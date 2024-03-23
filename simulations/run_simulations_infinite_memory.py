from datetime import datetime, timedelta
from TCPTraceConst import TCPTraceConst
import pickle
import os

##################################################

def compare_tcptrace_and_dartmeminf_rtts(dart_rtts):

    TCPTRACE_ALL_RTTS_PATH = "./intermediate/tcptrace_rtts_all.pickle"
    with open(TCPTRACE_ALL_RTTS_PATH, "rb") as fp:
        tcptrace_rtts = pickle.load(fp)

    for fkey in tcptrace_rtts:
        if len(tcptrace_rtts[fkey]) > len(dart_rtts[fkey]):
            print(fkey)
            print(tcptrace_rtts[fkey])
            print(dart_rtts[fkey])
            break

    return

##################################################

# def main():

#     t_format = "%Y-%m-%d %H:%M:%S"
#     t_start  = datetime.now()
#     print("Starting simulations at time: {}".format(t_start.strftime(t_format)))

#     local_path = "./intermediate/dart_simulations_infmem"

#     tcptrace_const_syn   = TCPTraceConst(local_path, 2000)
#     tcptrace_const_nosyn = TCPTraceConst(local_path, 2000)
    
#     process_packets_path = "./intermediate/smallFlows.pickle"
#     with open(process_packets_path, "rb") as packets_fp:
#         packets = pickle.load(packets_fp)
    
#     packets_count = 0

#     for packet_data in packets:

#         packet = {}
#         packet["pktno"], packet["timestamp"], packet["ipsrc"], packet["ipdst"], packet["tcpsrc"], \
#             packet["tcpdst"], packet["tcpflags"], packet["seqno"], packet["ackno"], packet["pktsize"] = packet_data
#         packet["tcpflags"] = packet["tcpflags"][2:]

#         if packets_count == 0:
#             tcptrace_const_syn._firstEntryTime   = packet["timestamp"]
#             tcptrace_const_nosyn._firstEntryTime = packet["timestamp"]
            
#         tcptrace_const_syn.process_tcptrace_SEQ(packet, allow_syn=True)
#         tcptrace_const_nosyn.process_tcptrace_SEQ(packet, allow_syn=False)

#         tcptrace_const_syn.process_tcptrace_ACK(packet, allow_syn=True)
#         tcptrace_const_nosyn.process_tcptrace_ACK(packet, allow_syn=False)

#         # print("tcptrace with SYN:")
#         # print(tcptrace_const_syn._tcptrace_flow_table)
#         # print(tcptrace_const_syn._tcptrace_packet_table)
#         # print(tcptrace_const_syn._tcptrace_sample_count)
#         # print(tcptrace_const_syn._tcptrace_rtt_samples)

#         # print("tcptrace with no SYN:")
#         # print(tcptrace_const_nosyn._tcptrace_flow_table)
#         # print(tcptrace_const_nosyn._tcptrace_packet_table)
#         # print(tcptrace_const_nosyn._tcptrace_sample_count)
#         # print(tcptrace_const_nosyn._tcptrace_rtt_samples)

#         # if packets_count == 10:
#         #     break
            
#         packets_count += 1

import threading
import time
import random
import hashlib
import pickle
from datetime import datetime, timedelta
import os
class MultiPipelineSwitch:
    def __init__(self, local_path, num_pipelines, tcptrace_const_syn, tcptrace_const_nosyn):
        self.local_path = local_path
        self.num_pipelines = num_pipelines
        self.pipelines = [[] for _ in range(num_pipelines)]
        self.locks = [threading.Lock() for _ in range(num_pipelines)]
        self.completed_packets = 0

        self.arr_tcptrace_const_syn = [tcptrace_const_syn]
        self.arr_tcptrace_const_nosyn = [tcptrace_const_nosyn]

    def update_pipelines(self, packet, pipeline_index):
        # Process tcptrace data
       for index in range(self.num_pipelines):
            if index == pipeline_index:
                continue
            tcptrace_const_syn = self.arr_tcptrace_const_syn[index]
            tcptrace_const_nosyn = self.arr_tcptrace_const_nosyn[index]
            tcptrace_const_syn.process_tcptrace_SEQ(packet, allow_syn=True)
            tcptrace_const_nosyn.process_tcptrace_SEQ(packet, allow_syn=False)
            tcptrace_const_syn.process_tcptrace_ACK(packet, allow_syn=True)
            tcptrace_const_nosyn.process_tcptrace_ACK(packet, allow_syn=False)

    def process_packet(self, pipeline_index):
        # Process tcptrace data
        while self.pipelines[pipeline_index]:
            packet = self.pipelines[pipeline_index].pop(0)
            tcptrace_const_syn = self.arr_tcptrace_const_syn[pipeline_index]
            tcptrace_const_nosyn = self.arr_tcptrace_const_nosyn[pipeline_index]
            tcptrace_const_syn.process_tcptrace_SEQ(packet, allow_syn=True)
            tcptrace_const_nosyn.process_tcptrace_SEQ(packet, allow_syn=False)
            tcptrace_const_syn.process_tcptrace_ACK(packet, allow_syn=True)
            tcptrace_const_nosyn.process_tcptrace_ACK(packet, allow_syn=False)
            self.completed_packets += 1

            self.update_pipelines(packet, pipeline_index)

    def receive_packet(self, packet):
        pipeline_index = self.calculate_pipeline_index(packet)
        self.pipelines[pipeline_index].append(packet)
        self.process_packet(pipeline_index)

    def calculate_pipeline_index(self, packet):
        # Calculate hash based on source and destination IP addresses
        hash_input = str(packet["ipsrc"]) + "-" + str(packet["ipdst"])
        hash_value = int(hashlib.sha256(hash_input.encode()).hexdigest(), 16)
        return hash_value % self.num_pipelines

    def start_processing(self, TOTAL_PACKETS):
        while self.completed_packets < TOTAL_PACKETS:
            for pipeline_index in range(self.num_pipelines):
                self.process_packet(pipeline_index)

    def initialize_buffers(self, timestamp):
        self.arr_tcptrace_const_syn[0]._firstEntryTime   = timestamp
        self.arr_tcptrace_const_nosyn[0]._firstEntryTime = timestamp

        for _ in range(self.num_pipelines - 1):
            self.arr_tcptrace_const_syn.append(TCPTraceConst(self.local_path, 2000))
            self.arr_tcptrace_const_syn[-1]._firstEntryTime   = timestamp
            self.arr_tcptrace_const_nosyn.append(TCPTraceConst(self.local_path, 2000))
            self.arr_tcptrace_const_nosyn[-1]._firstEntryTime   = timestamp
        
        print(self.arr_tcptrace_const_syn)
def main():
    t_format = "%Y-%m-%d %H:%M:%S"
    t_start  = datetime.now()
    print("Starting simulations at time: {}".format(t_start.strftime(t_format)))

    local_path = "./intermediate/dart_simulations_infmem"

    tcptrace_const_syn   = TCPTraceConst(local_path, 2000)
    tcptrace_const_nosyn = TCPTraceConst(local_path, 2000)
    
    process_packets_path = "./intermediate/smallFlows.pickle"
    with open(process_packets_path, "rb") as packets_fp:
        packets = pickle.load(packets_fp)
    
    packets_count = 0

    NUM_PIPELINES = 4
    TOTAL_PACKETS = len(packets)
    print(TOTAL_PACKETS)
    print(packets[2])

    switch = MultiPipelineSwitch(local_path, NUM_PIPELINES, tcptrace_const_syn, tcptrace_const_nosyn)

    # processing_thread = threading.Thread(target=switch.start_processing, args=(TOTAL_PACKETS,))
    # processing_thread.start()

    for packet_data in packets:
        packet = {}
        packet["pktno"], packet["timestamp"], packet["ipsrc"], packet["ipdst"], packet["tcpsrc"], \
        packet["tcpdst"], packet["tcpflags"], packet["seqno"], packet["ackno"], packet["pktsize"] = packet_data
        packet["tcpflags"] = packet["tcpflags"][2:]

        if packets_count == 0:
            switch.initialize_buffers(packet["timestamp"])
        switch.receive_packet(packet)
        packets_count += 1
    
    # processing_thread.join()
    
    tcptrace_const_syn.concludeRTTDict()
    tcptrace_const_nosyn.concludeRTTDict()

    tcptrace_syn_rtt_all = []
    
    for flow_key in tcptrace_const_syn._tcptrace_rtt_samples:
        # print(flow_key)
        # print("--")
        # print(tcptrace_const_syn._tcptrace_rtt_samples[flow_key])
        tcptrace_syn_rtt_all.extend([t[1] for t in tcptrace_const_syn._tcptrace_rtt_samples[flow_key]])
    # print(tcptrace_const_syn._tcptrace_rtt_samples)
    # print(tcptrace_syn_rtt_all)
    tcptrace_nosyn_rtt_all = []
    for flow_key in tcptrace_const_nosyn._tcptrace_rtt_samples:
        tcptrace_nosyn_rtt_all.extend([t[1] for t in tcptrace_const_nosyn._tcptrace_rtt_samples[flow_key]])

    with open(os.path.join(local_path, "rtt_samples_tcptrace_const_syn.txt"), "w") as fp:
        lines = ["{}".format(point) for point in tcptrace_syn_rtt_all]
        fp.write("\n".join(lines))

        dart_inf_mem_syn = [float(line.strip()) for line in lines]
        print("Dart(+SYN): {}".format(len(dart_inf_mem_syn)))

    
    with open(os.path.join(local_path, "rtt_samples_tcptrace_const_nosyn.txt"), "w") as fp:
        lines = ["{}".format(point) for point in tcptrace_nosyn_rtt_all]
        fp.write("\n".join(lines))

        dart_inf_mem_nosyn = [float(line.strip()) for line in lines]
        print("Dart(-SYN): {}".format(len(dart_inf_mem_nosyn)))

    t_end = datetime.now()
    t_elapsed = round((t_end - t_start)/timedelta(minutes=1), 2)
    print("Simulations complete at time: {}".format(t_end.strftime(t_format)))
    print("Time elapsed: {} mins.".format(t_elapsed))

    # compare_tcptrace_and_dartmeminf_rtts(tcptrace_const_syn._tcptrace_rtt_samples)

##################################################

if __name__ == "__main__":
    main()

##################################################
