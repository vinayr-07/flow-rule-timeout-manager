from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER, DEAD_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.ofproto import ofproto_v1_3
from ryu.lib.packet import packet, ethernet, ether_types, ipv4
from ryu.lib import hub
import datetime, time

IDLE_TIMEOUT = 10
HARD_TIMEOUT = 30
BLOCKED_HOSTS = ['10.0.0.4']

class FlowTimeoutManager(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]
    def __init__(self, *args, **kwargs):
        super(FlowTimeoutManager, self).__init__(*args, **kwargs)
        self.mac_to_port = {}
        self.flow_count = 0
        self.expired_flows = []
        self.datapaths = {}
        self.monitor_thread = hub.spawn(self._monitor_loop)
        self.logger.info("=" * 60)
        self.logger.info("  Flow Rule Timeout Manager Started")
        self.logger.info(f"  IDLE_TIMEOUT  = {IDLE_TIMEOUT}s")
        self.logger.info(f"  HARD_TIMEOUT  = {HARD_TIMEOUT}s")
        self.logger.info(f"  BLOCKED_HOSTS = {BLOCKED_HOSTS}")
        self.logger.info("=" * 60)

    def _monitor_loop(self):
        while True:
            for dp in list(self.datapaths.values()):
                parser = dp.ofproto_parser
                dp.send_msg(parser.OFPFlowStatsRequest(dp))
            hub.sleep(5)

    @set_ev_cls(ofp_event.EventOFPFlowStatsReply, MAIN_DISPATCHER)
    def flow_stats_reply_handler(self, ev):
        body = ev.msg.body
        dpid = ev.msg.datapath.id
        if body:
            self.logger.info(f"\n[FLOW TABLE] Switch dpid={dpid} - {len(body)} active flow(s):")
            for stat in body:
                if stat.priority > 0:
                    self.logger.info(f"  priority={stat.priority} idle={stat.idle_timeout}s hard={stat.hard_timeout}s duration={stat.duration_sec}s packets={stat.packet_count}")

    @set_ev_cls(ofp_event.EventOFPStateChange, [MAIN_DISPATCHER, DEAD_DISPATCHER])
    def state_change_handler(self, ev):
        datapath = ev.datapath
        if ev.state == MAIN_DISPATCHER:
            self.datapaths[datapath.id] = datapath
            self.logger.info(f"[SWITCH] Connected: dpid={datapath.id}")
        elif ev.state == DEAD_DISPATCHER:
            self.datapaths.pop(datapath.id, None)
            self.logger.info(f"[SWITCH] Disconnected: dpid={datapath.id}")

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        datapath = ev.msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        match = parser.OFPMatch()
        actions = [parser.OFPActionOutput(ofproto.OFPP_CONTROLLER, ofproto.OFPCML_NO_BUFFER)]
        self._add_flow(datapath, 0, match, actions, idle_timeout=0, hard_timeout=0)
        self.logger.info(f"[SETUP] Table-miss installed on dpid={datapath.id}")

    def _add_flow(self, datapath, priority, match, actions, idle_timeout=IDLE_TIMEOUT, hard_timeout=HARD_TIMEOUT, buffer_id=None):
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS, actions)]
        kwargs = dict(datapath=datapath, priority=priority, match=match, instructions=inst, idle_timeout=idle_timeout, hard_timeout=hard_timeout)
        if buffer_id and buffer_id != ofproto.OFP_NO_BUFFER:
            kwargs['buffer_id'] = buffer_id
        datapath.send_msg(parser.OFPFlowMod(**kwargs))
        self.flow_count += 1
        self.logger.info(f"[FLOW INSTALLED] dpid={datapath.id} priority={priority} idle={idle_timeout}s hard={hard_timeout}s total={self.flow_count}")

    @set_ev_cls(ofp_event.EventOFPFlowRemoved, MAIN_DISPATCHER)
    def flow_removed_handler(self, ev):
        msg = ev.msg
        dp = msg.datapath
        ofproto = dp.ofproto
        reason_map = {ofproto.OFPRR_IDLE_TIMEOUT: "IDLE_TIMEOUT", ofproto.OFPRR_HARD_TIMEOUT: "HARD_TIMEOUT", ofproto.OFPRR_DELETE: "DELETE"}
        reason = reason_map.get(msg.reason, "UNKNOWN")
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        self.expired_flows.append({"time": timestamp, "reason": reason})
        self.logger.info(f"\n[FLOW EXPIRED] @ {timestamp} reason={reason} dpid={dp.id} duration={msg.duration_sec}s packets={msg.packet_count} bytes={msg.byte_count}")
        self.logger.info(f"[STATS] Total expired flows: {len(self.expired_flows)}")

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def packet_in_handler(self, ev):
        msg = ev.msg
        datapath = msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        in_port = msg.match['in_port']
        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocols(ethernet.ethernet)[0]
        if eth.ethertype == ether_types.ETH_TYPE_LLDP:
            return
        dst_mac = eth.dst
        src_mac = eth.src
        dpid = datapath.id
        self.mac_to_port.setdefault(dpid, {})
        self.mac_to_port[dpid][src_mac] = in_port
        ip_pkt = pkt.get_protocol(ipv4.ipv4)
        if ip_pkt:
            if ip_pkt.src in BLOCKED_HOSTS or ip_pkt.dst in BLOCKED_HOSTS:
                self.logger.info(f"[BLOCKED] Packet from {ip_pkt.src} to {ip_pkt.dst} — DROP rule installed.")
                match = parser.OFPMatch(eth_type=ether_types.ETH_TYPE_IP, ipv4_src=ip_pkt.src)
                self._add_flow(datapath, 10, match, [], idle_timeout=IDLE_TIMEOUT, hard_timeout=HARD_TIMEOUT)
                return
        out_port = self.mac_to_port[dpid].get(dst_mac, ofproto.OFPP_FLOOD)
        actions = [parser.OFPActionOutput(out_port)]
        if out_port != ofproto.OFPP_FLOOD:
            match = parser.OFPMatch(in_port=in_port, eth_dst=dst_mac, eth_src=src_mac)
            if msg.buffer_id != ofproto.OFP_NO_BUFFER:
                self._add_flow(datapath, 1, match, actions, buffer_id=msg.buffer_id)
                return
            else:
                self._add_flow(datapath, 1, match, actions)
        data = None if msg.buffer_id != ofproto.OFP_NO_BUFFER else msg.data
        datapath.send_msg(parser.OFPPacketOut(datapath=datapath, buffer_id=msg.buffer_id, in_port=in_port, actions=actions, data=data))
