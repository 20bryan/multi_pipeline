from datetime import datetime, timedelta
from ipaddress import IPv4Address
import itertools
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import seaborn as sns
import sys
from TCPTraceConst import TCPTraceConst
import pickle
import os
import numpy as np

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
        self.processed_packets_by_pipeline = [0] * num_pipelines

        self.arr_tcptrace_const_syn = [tcptrace_const_syn]
        self.arr_tcptrace_const_nosyn = [tcptrace_const_nosyn]
        self.cumulative_processed_packets = []
        self.timestamps = []

    def update_pipelines(self, packet, pipeline_index):
        # Process tcptrace data
       for index in range(self.num_pipelines):
            if index == pipeline_index:
                continue
            self.recirculate_packet_to_pipeline(packet, index)

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
        self.cumulative_processed_packets.append(sum(pip_count for pip_count in self.processed_packets_by_pipeline))
        self.timestamps.append((packet["timestamp"] - self.arr_tcptrace_const_syn[pipeline_index]._firstEntryTime)/timedelta(milliseconds=1))


    def recirculate_packet_to_pipeline(self, packet, pipeline_index):
        tcptrace_const_syn = self.arr_tcptrace_const_syn[pipeline_index]
        tcptrace_const_nosyn = self.arr_tcptrace_const_nosyn[pipeline_index]
        tcptrace_const_syn.process_tcptrace_SEQ(packet, allow_syn=True)
        tcptrace_const_nosyn.process_tcptrace_SEQ(packet, allow_syn=False)
        tcptrace_const_syn.process_tcptrace_ACK(packet, allow_syn=True)
        tcptrace_const_nosyn.process_tcptrace_ACK(packet, allow_syn=False)
        
        self.processed_packets_by_pipeline[pipeline_index] += 1

    def receive_packet_sharding(self, packet):
        pipeline_index = self.calculate_pipeline_index(packet)
        self.pipelines[pipeline_index].append(packet)
        self.process_packet_sharding(pipeline_index)
        self.cumulative_processed_packets.append(sum(pip_count for pip_count in self.processed_packets_by_pipeline))
        self.timestamps.append((packet["timestamp"] - self.arr_tcptrace_const_syn[pipeline_index]._firstEntryTime)/timedelta(milliseconds=1))

    def process_packet_sharding(self, pipeline_index):
        # Process tcptrace data
        while self.pipelines[pipeline_index]:
            packet = self.pipelines[pipeline_index].pop(0)
            destination_pipeline_index = self.calculate_sharding_pipeline_index(packet)
            flow_key = (packet["ipsrc"], packet["ipdst"], packet["tcpsrc"], packet["tcpdst"])
            print("send packet with flow key", flow_key, "to pipeline index" , destination_pipeline_index)
            self.recirculate_packet_to_pipeline(packet, destination_pipeline_index)
            self.completed_packets += 1
                   

    def receive_packet_ingress_leader(self, packet):
        pipeline_index = self.calculate_pipeline_index(packet)
        self.pipelines[pipeline_index].append(packet)
        self.process_packet_ingress_leader(pipeline_index)
        self.cumulative_processed_packets.append(sum(pip_count for pip_count in self.processed_packets_by_pipeline))
        self.timestamps.append((packet["timestamp"] - self.arr_tcptrace_const_syn[pipeline_index]._firstEntryTime)/timedelta(milliseconds=1))



    def process_packet_ingress_leader(self, pipeline_index):
        # Process tcptrace data
        while self.pipelines[pipeline_index]:
            packet = self.pipelines[pipeline_index].pop(0)
            destination_pipeline_index = 0
            self.recirculate_packet_to_pipeline(packet, destination_pipeline_index)
            self.completed_packets += 1

    def calculate_pipeline_index(self, packet):
        # Calculate hash based on source and destination IP addresses
        hash_input = str(packet["ipsrc"]) + "-" + str(packet["ipdst"])
        hash_value = int(hashlib.sha256(hash_input.encode()).hexdigest(), 16)
        return hash_value % self.num_pipelines
    
    def calculate_sharding_pipeline_index(self, packet):
        # Calculate hash based on flow

        flow_key = (packet["ipsrc"], packet["ipdst"], packet["tcpsrc"], packet["tcpdst"])
        keys = sorted([item for item in flow_key[:2]]) + (sorted([item for item in flow_key[2:]]))
        hash_input =  "-".join([str(key) for key in keys])
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
            self.arr_tcptrace_const_syn.append(TCPTraceConst(self.local_path, 2000, True))
            self.arr_tcptrace_const_syn[-1]._firstEntryTime   = timestamp
            self.arr_tcptrace_const_nosyn.append(TCPTraceConst(self.local_path, 2000, True))
            self.arr_tcptrace_const_nosyn[-1]._firstEntryTime   = timestamp
        

def main(argument = None):
    t_format = "%Y-%m-%d %H:%M:%S"
    t_start  = datetime.now()
    print("Starting simulations at time: {}".format(t_start.strftime(t_format)))

    local_path = "./intermediate/dart_simulations_infmem"

    tcptrace_const_syn   = TCPTraceConst(local_path, 2000, True)
    tcptrace_const_nosyn = TCPTraceConst(local_path, 2000, True)
    
    process_packets_path = "./intermediate/smallFlows.pickle"
    with open(process_packets_path, "rb") as packets_fp:
        packets = pickle.load(packets_fp)
    
    packets_count = 0


    # try 1 pipeline, 2 pipelines, 4 pipelines, then 16 pipelines
    NUM_PIPELINES = 16
    TOTAL_PACKETS = len(packets)
    # print(TOTAL_PACKETS)
    # print(packets[2])

    switch = MultiPipelineSwitch(local_path, NUM_PIPELINES, tcptrace_const_syn, tcptrace_const_nosyn)

    # processing_thread = threading.Thread(target=switch.start_processing, args=(TOTAL_PACKETS,))
    # processing_thread.start()

    for packet_data in packets:
        packet = {}
        packet["pktno"], packet["timestamp"], packet["ipsrc"], packet["ipdst"], packet["tcpsrc"], \
        packet["tcpdst"], packet["tcpflags"], packet["seqno"], packet["ackno"], packet["pktsize"] = packet_data
        packet["tcpflags"] = packet["tcpflags"][2:]

        # flow_key1 = (IPv4Address('10.0.2.15'), IPv4Address('64.4.35.57'), 2550, 1863)
        # flow_key1rev = (IPv4Address('64.4.35.57'), IPv4Address('10.0.2.15'), 1863, 2550)
        # flow_key2 = (IPv4Address('10.0.2.15'), IPv4Address('64.4.35.57'), 2550, 61863)
        # flow_key2rev = ( IPv4Address('64.4.35.57'), IPv4Address('10.0.2.15'), 61863, 2550)

        if packets_count == 0:
            switch.initialize_buffers(packet["timestamp"])
        
        if argument is None:
            switch.receive_packet(packet)
        elif argument == "ingress_leader":
            switch.receive_packet_ingress_leader(packet)
        elif argument == "sharding":
            switch.receive_packet_sharding(packet)
        else:
            raise ValueError("Invalid argument: " + str(argument))
        packets_count += 1

        latest_timestamp = packet["timestamp"]
    
    # processing_thread.join()

    print(switch.completed_packets)
    print(switch.processed_packets_by_pipeline)
    
    # tcptrace_const_syn.concludeRTTDict()
    # tcptrace_const_nosyn.concludeRTTDict()

    tcptrace_syn_rtt_all = []
    tcptrace_nosyn_rtt_all = []
    for syn, nosyn in zip(switch.arr_tcptrace_const_syn, switch.arr_tcptrace_const_nosyn):
        tcptrace_const_syn = syn
        tcptrace_const_nosyn = nosyn

        tcptrace_const_syn.concludeRTTDict()
        tcptrace_const_nosyn.concludeRTTDict()
        for flow_key in tcptrace_const_syn._tcptrace_rtt_samples:
            # print(flow_key)
            # print("--")
            # print(tcptrace_const_syn._tcptrace_rtt_samples[flow_key])
            tcptrace_syn_rtt_all.extend([t[1] for t in tcptrace_const_syn._tcptrace_rtt_samples[flow_key]])
        # print(tcptrace_const_syn._tcptrace_rtt_samples)
        # print(tcptrace_syn_rtt_all)
        for flow_key in tcptrace_const_nosyn._tcptrace_rtt_samples:
            tcptrace_nosyn_rtt_all.extend([t[1] for t in tcptrace_const_nosyn._tcptrace_rtt_samples[flow_key]])
        
        with open(os.path.join(local_path, "rtt_samples_tcptrace_const_synDEBUG13.txt"), "a") as fp:
            lines = ["{}".format(sample) for sample in sorted(tcptrace_const_syn._tcptrace_rtt_samples.items())]
            fp.write("\n".join(lines))

                
        if argument != "sharding":
            break
    

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

    print("RTT average for (+SYN): %.2f" % (sum(dart_inf_mem_syn) / len(dart_inf_mem_syn)))
    if len(tcptrace_const_syn.duplicate_rtts) > 0:
        print("rtt excess time is ", sum(tcptrace_const_syn.duplicate_rtts) / len(tcptrace_const_syn.duplicate_rtts))
        print("RTT WITH EXCESS average for (+SYN): %.2f" % ((sum(dart_inf_mem_syn) + sum(tcptrace_const_syn.duplicate_rtts))/ (len(tcptrace_const_syn.duplicate_rtts) + len(dart_inf_mem_syn))))

    print("RTT average for (-SYN): %.2f" % (sum(dart_inf_mem_nosyn) / len(dart_inf_mem_nosyn)))
    # compare_tcptrace_and_dartmeminf_rtts(tcptrace_const_syn._tcptrace_rtt_samples)


    tcptrace_const_syn.plot_tcptrace_stats(latest_timestamp)

    def plot_aggregate_data(x_data, y_datas, xlabel, ylabel, title, plot_filename, resultsPath, isFlow = False):
        sns_colors = itertools.cycle(sns.color_palette("bright"))

        plt.figure(figsize=(6,4))
        time_x = [t/1000 for t in x_data]

        
        color = next(sns_colors)
        plt.plot(time_x, y_datas, color=color, linestyle="-", label = 'Optimized Duplication')

        if not isFlow:
            plt.axhline(y=4000, color='red', linestyle='--', label='Theoretical Lower Bound')
        else:
            plt.axhline(y=370, color='red', linestyle='--', label='Theoretical Lower Bound')

        plt.xlabel(xlabel)
        plt.ylabel(ylabel)
        plt.title(title)
        plt.tight_layout()
        plt.legend()
        plot_path = os.path.join(resultsPath, plot_filename)
        plt.savefig(plot_path, dpi=300)
        plt.clf()
        plt.close("all")

    # Calculate aggregate flow data
    aggregate_packet_data = []
    overall_packet_times = []
    for index, obj in enumerate(switch.arr_tcptrace_const_syn):
        overall_packet_times.extend(zip(obj._snapshotTime, obj._intervalActivePackets, [index] * len(obj._snapshotTime)))
    
    overall_packet_times.sort()

    aggregate_packet_times= []
    running_sum = 0
    last_val_for_pipeline = [0] * 16
    for t, val, index in overall_packet_times:
        running_sum += val
        running_sum -= last_val_for_pipeline[index]
        last_val_for_pipeline[index] = val
        aggregate_packet_times.append((t, running_sum))


    # print(aggregate_packet_times)
    # print("DONE")
    # print(len(aggregate_packet_times))
    # print(overall_packet_times)

    overall_flow_times = []
    for index, obj in enumerate(switch.arr_tcptrace_const_syn):
        overall_flow_times.extend(zip(obj._snapshotTime, obj._intervalActiveFlows, [index] * len(obj._snapshotTime)))
    
    overall_flow_times.sort()

    aggregate_flow_times= []
    running_sum = 0
    last_val_for_pipeline = [0] * 16
    for t, val, index in overall_flow_times:
        running_sum += val
        running_sum -= last_val_for_pipeline[index]
        last_val_for_pipeline[index] = val
        aggregate_flow_times.append((t, running_sum))


    # Plot aggregate No. of flow records vs. time
    plot_aggregate_data(
        [item[0] for item in aggregate_flow_times],
        [item[1] for item in aggregate_flow_times],
        "Time (sec.)",
        "Aggregate Count",
        "Aggregate Flow Records vs. Time",
        "tcptrace_aggregate_flows_records.png",
        switch.arr_tcptrace_const_syn[0]._resultsPath,
        True
    )

    # Plot aggregate No. of packet records vs. time
    plot_aggregate_data(
        [item[0] for item in aggregate_packet_times],
        [item[1] for item in aggregate_packet_times],
        "Time (sec.)",
        "Aggregate Count",
        "Aggregate Packet Records vs. Time",
        "tcptrace_aggregate_packets_records.png",
        switch.arr_tcptrace_const_syn[0]._resultsPath,
        False          
    )

    # Extract aggregate flow and packet data from arr_tcptrace_const_syn
    aggregate_flow_data = [obj._intervalActiveFlows for obj in switch.arr_tcptrace_const_syn]
    aggregate_packet_data = [obj._intervalActivePackets for obj in switch.arr_tcptrace_const_syn]


    def plot_individual_data(x_datas, y_datas, y_labels, xlabel, ylabel, title, plot_filename, resultsPath, isNormalized = False):
        sns_colors = itertools.cycle(sns.color_palette("bright"))

        plt.figure(figsize=(6,4))

        for i, (x_data, y_data, label) in enumerate(zip(x_datas, y_datas, y_labels)):
            color = next(sns_colors)
            time_x = [t/1000 for t in x_data]
            if isNormalized:
                if i == len(y_datas) - 1:
                    aggregate_color = '#9467bd'
                    plt.plot(time_x, y_data, label=label, color=aggregate_color, linestyle="-", linewidth=2.5)
                else:
                    plt.plot(time_x, y_data, label=label, color=color, linestyle="--", linewidth = 1)
            else:
                plt.plot(time_x, y_data, label=label, color=color, linestyle="-")

        plt.xlabel(xlabel)
        plt.ylabel(ylabel)
        plt.title(title)
        plt.legend()
        plt.tight_layout()

        # plt.ylim(bottom=0, top=max(max(y) for y in y_datas) * 1.1)
        if isNormalized:
            plt.gca().yaxis.set_major_formatter(ticker.FuncFormatter(lambda x, _: f'{x:.0f}%'))
        plot_path = os.path.join(resultsPath, plot_filename)
        plt.savefig(plot_path, dpi=300)
        plt.clf()
        plt.close("all")

    # Plot individual No. of flow records vs. time
    plot_individual_data(
        [node._snapshotTime for node in switch.arr_tcptrace_const_syn],  # Assuming all objects have the same time data
        aggregate_flow_data,
        ["Ingress Pipeline {}".format(i) for i in range(len(switch.arr_tcptrace_const_syn))],
        "Time (sec.)",
        "No. of flow records",
        "Individual Flow Records vs. Time",
        "tcptrace_individual_flows_records.png",
        switch.arr_tcptrace_const_syn[0]._resultsPath
    )

    # Plot individual No. of packet records vs. time
    plot_individual_data(
        [node._snapshotTime for node in switch.arr_tcptrace_const_syn],  # Assuming all objects have the same time data
        aggregate_packet_data,
        ["Ingress Pipeline {}".format(i) for i in range(len(switch.arr_tcptrace_const_syn))],
        "Time (sec.)",
        "No. of packet records",
        "Individual Packet Records vs. Time",
        "tcptrace_individual_packet_records.png",
        switch.arr_tcptrace_const_syn[0]._resultsPath
    )

    # Plot individual No. of flow records vs. time
    # print(switch.cumulative_processed_packets)
    # print(switch.timestamps)

    plot_individual_data(
        [switch.timestamps],
        [switch.cumulative_processed_packets], 
        # [node._snapshotTime for node in switch.arr_tcptrace_const_syn],  # Assuming all objects have the same time data
        # [[index + 1 for index, _ in enumerate(flow)] for flow in aggregate_flow_data],
        ["Ingress Pipeline {}".format(i) for i in range(len(switch.arr_tcptrace_const_syn))],
        "Time (sec.)",
        "No. of recirculations",
        "Packet Recirculations vs. Time",
        "tcptrace_recirculation_packet_records.png",
        switch.arr_tcptrace_const_syn[0]._resultsPath,
    )

    np.savetxt('aggregate_flows_n=16.txt', aggregate_flow_times)
    np.savetxt('aggregate_packets_n=16.txt', aggregate_packet_times)

    # setup1_x_data = np.loadtxt('setup1_x_data.txt')
    # setup1_y_data = np.loadtxt('setup1_y_data.txt')
    # setup2_x_data = np.loadtxt('setup2_x_data.txt')
    # setup2_y_data = np.loadtxt('setup2_y_data.txt')

    # # Plot the data from all setups on one graph
    # plot_individual_data(
    #     [setup1_x_data, setup2_x_data],
    #     [setup1_y_data, setup2_y_data],
    #     ["Setup 1", "Setup 2"],
    #     "Time (sec.)",
    #     "No. of recirculations",
    #     "Packet Recirculations vs. Time",
    #     "final_comparison_plot.png"
    # )

    # total_flow_time = aggregate_flow_times[-1][1]
    # normalized_flow_times = [(t / total_flow_time) * 100 for t in [item[1] for item in aggregate_flow_times]]
    # normalized_aggregate_flow_data = []
    # for flow in aggregate_flow_data:
    #     total_time = flow[-1]
    #     normalized_aggregate_flow_data.append([(t / total_time) * 100 for t in flow])
    
    # normalized_aggregate_flow_data.append(normalized_flow_times)
    # normalized_times = [node._snapshotTime for node in switch.arr_tcptrace_const_syn] + [[item[0] for item in aggregate_flow_times]]
    

    # plot_individual_data(
    #     normalized_times,  # Assuming all objects have the same time data
    #     normalized_aggregate_flow_data,
    #     ["Ingress Pipeline {}".format(i) for i in range(len(switch.arr_tcptrace_const_syn))] + ["Aggregate Pipelines"],
    #     "Time (sec.)",
    #     "No. of flow records (Normalized)",
    #     "Normalized Flow Records vs. Time",
    #     "tcptrace_normalized_flows_records.png",
    #     switch.arr_tcptrace_const_syn[0]._resultsPath,
    #     True
    # )

    # total_flow_time = aggregate_packet_times[-1][1]
    # normalized_packet_times = [(t / total_flow_time) * 100 for t in [item[1] for item in aggregate_packet_times]]
    # normalized_aggregate_packet_data = []
    # for flow in aggregate_packet_data:
    #     total_time = flow[-1]
    #     normalized_aggregate_packet_data.append([(t / total_time) * 100 for t in flow])
    
    # normalized_aggregate_packet_data.append(normalized_packet_times)
    # normalized_times = [node._snapshotTime for node in switch.arr_tcptrace_const_syn] + [[item[0] for item in aggregate_packet_times]]
    

    # plot_individual_data(
    #     normalized_times,  # Assuming all objects have the same time data
    #     normalized_aggregate_packet_data,
    #     ["Ingress Pipeline {}".format(i) for i in range(len(switch.arr_tcptrace_const_syn))] + ["Aggregate Pipelines"],
    #     "Time (sec.)",
    #     "No. of packet records (Normalized)",
    #     "Normalized Packet Records vs. Time",
    #     "tcptrace_normalized_packets_records.png",
    #     switch.arr_tcptrace_const_syn[0]._resultsPath,
    #     True
    # )


    # def plot_individual_data(x_datas, y_datas, labels, xlabel, ylabel, title, plot_filename, resultsPath):
    #     plt.figure(figsize=(8, 6))

    #     for x_data, y_data, label in zip(x_datas, y_datas, labels):
    #         plt.plot(x_data, y_data, label=label)

    #     plt.xlabel(xlabel)
    #     plt.ylabel(ylabel)
    #     plt.title(title)
    #     plt.legend()
    #     plt.grid(True)
    #     plt.tight_layout()
    #     plt.savefig(plot_filename)
    #     plt.show()
    #     plot_path = os.path.join(resultsPath, plot_filename)
    #     plt.savefig(plot_path, dpi=300)


    # Assuming you have already stored the x and y data for each setup into separate files
    # Now, let's read the data from the files
    setupbest_x_data = np.loadtxt('switch_cumulative_processed_packets.txt')
    setupbest_y_data = np.loadtxt('switch_timestamps.txt')
    setupnaive_x_data = np.loadtxt('switch_cumulative_processed_packets1.txt')
    setupnaive_y_data = np.loadtxt('switch_timestamps1.txt')
    setupopt_x_data = np.loadtxt('switch_cumulative_processed_packets2.txt')
    setupopt_y_data = np.loadtxt('switch_timestamps2.txt')

    plot_individual_data(
        [setupbest_y_data, setupnaive_y_data], # setupnaive_y_data],
        [setupbest_x_data, setupnaive_x_data], #, setupnaive_x_data],
        ["Sharding & Optimized Baseline", "Naive Baseline"],
        "Time (sec.)",
        "No. of recirculations",
        "Packet Recirculations vs. Time",
        "final_comparison_plot_with_line.png",
        switch.arr_tcptrace_const_syn[0]._resultsPath,
    )

    # Assuming you have already stored the x and y data for each setup into separate files
    # Now, let's read the data from the files
    setup1_x_data = np.loadtxt('aggregate_flows_n=1.txt')
    setup1_y_data = np.loadtxt('aggregate_packets_n=1.txt')
    setup2_x_data = np.loadtxt('aggregate_flows_n=2.txt')
    setup2_y_data = np.loadtxt('aggregate_packets_n=2.txt')
    setup4_x_data = np.loadtxt('aggregate_flows_n=4.txt')
    setup4_y_data = np.loadtxt('aggregate_packets_n=4.txt')
    setup16_x_data = np.loadtxt('aggregate_flows_n=16.txt')
    setup16_y_data = np.loadtxt('aggregate_packets_n=16.txt')

    plot_individual_data(
        [[item[0] for item in setup1_x_data], [item[0] for item in setup2_x_data], [item[0] for item in setup4_x_data], [item[0] for item in setup16_x_data]], # setupnaive_y_data],
        [[item[1] for item in setup1_x_data], [item[1] for item in setup2_x_data], [item[1] for item in setup4_x_data], [item[1] for item in setup16_x_data]], #, setupnaive_x_data],
        ["N = 1", "N = 2", "N = 4", "N = 16"],
        "Time (sec.)",
        "Aggregate Count",
        "Aggregate Packet Records vs. Time",
        "final_aggregate_packets_records.png",
        switch.arr_tcptrace_const_syn[0]._resultsPath,
    )




##################################################

if __name__ == "__main__":
    if len(sys.argv) == 1:
        main()  # Call main function without argument
    elif len(sys.argv) == 2:
        argument = sys.argv[1]
        main(argument)  # Call main function with the provided argument
    else:
        print("Usage: python script_name.py [argument]")
        sys.exit(1)
##################################################
