# 🔄 Flow Rule Timeout Manager — SDN Project #22

A Software Defined Networking (SDN) project implementing **timeout-based flow rule lifecycle management** using the **Ryu controller** and **Mininet** network emulator. This project demonstrates how OpenFlow flow rules are automatically removed after idle or hard timeout periods, and how blocked hosts are enforced using drop rules.

---

## 📋 Project Overview

| Item | Details |
|------|---------|
| **Project #** | 22 |
| **Topic** | Flow Rule Timeout Manager |
| **Controller** | Ryu (OpenFlow 1.3) |
| **Emulator** | Mininet |
| **Environment** | Ubuntu 22.04 (VMware) |
| **Python** | 3.11+ |
| **IDLE_TIMEOUT** | 10 seconds |
| **HARD_TIMEOUT** | 30 seconds |
| **Blocked Hosts** | `10.0.0.4` |

---

## 🎯 Objectives

- Configure idle and hard timeouts on OpenFlow flow rules
- Remove expired flow rules automatically via the switch
- Demonstrate the complete flow rule lifecycle (install → active → expire)
- Analyze timeout behavior using flow table monitoring
- Regression test: verify timeout behavior remains consistent across runs

---

## 🗂️ Project Structure

```
flow-rule-timeout-manager/
│
├── README.md
│
├── src/
│   ├── timeout_manager.py     # Ryu SDN controller
│   └── topology.py            # Mininet topology (4 hosts, 1 switch)
│
├── screenshots/
│   ├── T1-SS1-controller-started.png
│   ├── T1-SS2-blocked-flow-installed.png
│   ├── T1-SS3-flow-expired-timeout.png
│   ├── T2-SS1-scenario1-normal-forwarding.png
│   ├── T2-SS2-scenario2-blocked-host.png
│   └── T2-SS3-scenario5-regression-test.png
│
└── docs/
    └── project-report.pdf
```

---

## 🌐 Network Topology

```
        [Ryu Controller]
               |
           [s1 Switch]
          /    |    \    \
        h1    h2    h3    h4
   10.0.0.1  .0.2  .0.3  .0.4
  (allowed)(allowed)(allowed)(BLOCKED)
```

- **4 hosts** connected to **1 OVS switch**
- **Remote Ryu controller** at `127.0.0.1:6633`
- All links at **10 Mbps** bandwidth
- `h4 (10.0.0.4)` is permanently blocked via DROP rule

---

## ⚙️ Setup & Installation

### Prerequisites

```bash
sudo apt update
sudo apt install -y python3.11 python3.11-venv mininet
```

### Install Ryu

```bash
mkdir ~/ryu && cd ~/ryu
python3.11 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install setuptools==67.8.0 wheel
pip install ryu eventlet==0.35.2
```

### Clone & Setup

```bash
git clone https://github.com/YOUR_USERNAME/flow-rule-timeout-manager.git
cd flow-rule-timeout-manager
cp src/timeout_manager.py ~/ryu/project/
cp src/topology.py ~/ryu/project/
```

---

## 🚀 How to Run

> ⚠️ Always run `sudo mn -c` BEFORE starting Ryu to clean up any stale processes.

### Step 1 — Clean up

```bash
sudo mn -c
```

### Step 2 — Start Ryu Controller (Terminal 1)

```bash
cd ~/ryu
source venv/bin/activate
ryu-manager ~/ryu/project/timeout_manager.py --observe-links
```

Expected output:
```
Flow Rule Timeout Manager Started
IDLE_TIMEOUT  = 10s
HARD_TIMEOUT  = 30s
BLOCKED_HOSTS = ['10.0.0.4']
```

### Step 3 — Start Mininet Topology (Terminal 2)

```bash
source ~/ryu/venv/bin/activate
sudo python3 ~/ryu/project/topology.py
```

---

## 🧪 Test Scenarios

| Scenario | Description | Expected Result |
|----------|-------------|-----------------|
| **1** | Normal Forwarding — `h1 ping h2` | `0% packet loss` |
| **2** | Blocked Host — `h4 ping h1` | `100% packet loss` |
| **3** | Throughput Test — `h1 iperf h3` | ~9–10 Mbits/sec |
| **4** | Wait 15s for IDLE_TIMEOUT | Flow table drops from 7 → 3 → 1 |
| **5** | Regression Test — `h1 ping h2` again | `0% packet loss` ✅ |

### Manual Testing in Mininet CLI

```bash
mininet> h1 ping -c 4 10.0.0.2     # Scenario 1
mininet> h4 ping -c 4 -W 1 10.0.0.1  # Scenario 2
mininet> h1 ping -c 4 10.0.0.2     # Scenario 5 (after 15s)
```

---

## 📊 Flow Rule Lifecycle

```
Packet Arrives
     │
     ▼
Controller Installs Flow Rule
  idle_timeout = 10s
  hard_timeout = 30s
     │
     ▼
Switch Forwards Traffic
     │
     ├── No traffic for 10s ──► IDLE_TIMEOUT ──► Rule Removed
     │
     └── Rule age reaches 30s ─► HARD_TIMEOUT ──► Rule Removed
```

### Key Controller Logs

```
[FLOW INSTALLED]  dpid=1 priority=1 idle=10s hard=30s
[BLOCKED]         Packet from 10.0.0.4 to 10.0.0.1 — DROP rule installed.
[FLOW TABLE]      Switch dpid=1 - 7 active flow(s)   # Peak
[FLOW TABLE]      Switch dpid=1 - 1 active flow(s)   # After timeout
[FLOW INSTALLED]  dpid=1 priority=1 idle=10s hard=30s total=13  # Regression
```

---

## 🔑 Key Concepts

### idle_timeout
Removes a flow rule if **no matching packets** are received for the specified duration. Used to clean up stale forwarding rules when hosts stop communicating.

### hard_timeout
Removes a flow rule **regardless of traffic** once the timer expires. Guarantees that rules are periodically refreshed.

### OFPFlowRemoved
An OpenFlow event sent by the switch to the controller when a flow rule is removed, containing the reason (`IDLE_TIMEOUT`, `HARD_TIMEOUT`, or `DELETE`), duration, packet count, and byte count.

---

## 📸 Screenshots

### T1 — Controller Started
Shows Ryu controller initializing with timeout parameters and blocked host configuration.

### T1 — Blocked + Flow Install
Shows `[BLOCKED]` drop rule installed for `10.0.0.4` and normal forwarding rules at `priority=1`.

### T1 — Flow Timeout
Shows flow table reducing from 7 → 3 → 1 active flows as rules expire after idle timeout.

### T2 — Normal Forwarding
Scenario 1: `h1 ping h2` with `0% packet loss` and RTT ~1ms.

### T2 — Blocked Host
Scenario 2: `h4 ping h1` with `100% packet loss`.

### T2 — Regression Test
Scenario 5: `h1 ping h2` after timeout — flows re-installed automatically, `0% packet loss`.

---

## 📄 License

MIT License — Free to use for academic purposes.

---

## 👤 Author

**Vinay**
BTech Student — SDN & Network Programmability
Project #22 — Flow Rule Timeout Manager
