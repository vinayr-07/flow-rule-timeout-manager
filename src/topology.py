from mininet.net import Mininet
from mininet.node import RemoteController, OVSSwitch
from mininet.cli import CLI
from mininet.log import setLogLevel, info
from mininet.link import TCLink
import time

def run_topology():
    setLogLevel('info')
    net = Mininet(controller=RemoteController, switch=OVSSwitch, link=TCLink, autoSetMacs=True)
    c0 = net.addController('c0', controller=RemoteController, ip='127.0.0.1', port=6633)
    s1 = net.addSwitch('s1', protocols='OpenFlow13')
    h1 = net.addHost('h1', ip='10.0.0.1/24')
    h2 = net.addHost('h2', ip='10.0.0.2/24')
    h3 = net.addHost('h3', ip='10.0.0.3/24')
    h4 = net.addHost('h4', ip='10.0.0.4/24')
    net.addLink(h1, s1, bw=10)
    net.addLink(h2, s1, bw=10)
    net.addLink(h3, s1, bw=10)
    net.addLink(h4, s1, bw=10)
    net.start()
    info("\n" + "="*60 + "\n  FLOW RULE TIMEOUT MANAGER - TEST TOPOLOGY\n" + "="*60 + "\n")
    info("  h1=10.0.0.1(allowed) h2=10.0.0.2(allowed)\n  h3=10.0.0.3(allowed) h4=10.0.0.4(BLOCKED)\n" + "="*60 + "\n")
    info("*** Waiting for controller...\n")
    time.sleep(5)
    info("\n--- SCENARIO 1: Normal Forwarding (h1 -> h2) ---\n")
    info(h1.cmd('ping -c 4 10.0.0.2'))
    info("\n--- SCENARIO 2: Blocked Host (h4 -> h1) ---\n")
    info(h4.cmd('ping -c 4 -W 1 10.0.0.1'))
    info("\n--- SCENARIO 3: Throughput Test (h1 -> h3) ---\n")
    h3.cmd('iperf -s &')
    time.sleep(1)
    info(h1.cmd('iperf -c 10.0.0.3 -t 5'))
    h3.cmd('kill %iperf')
    info("\n--- SCENARIO 4: Waiting 15s for IDLE_TIMEOUT ---\n")
    info("Watch Terminal 1 for [FLOW EXPIRED] messages...\n")
    time.sleep(15)
    info("\n--- SCENARIO 5: Regression Test (h1 -> h2 after timeout) ---\n")
    info(h1.cmd('ping -c 4 10.0.0.2'))
    info("\n*** All scenarios done! Opening CLI...\n")
    CLI(net)
    net.stop()

if __name__ == '__main__':
    run_topology()
