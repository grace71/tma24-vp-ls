#! /usr/bin/python3
# -*- coding: utf-8 -*-
# Copyright 2024 Ramsha Rauf <rrauf@smith.edu>
#                Sophia Dai <sdai33@smith.edu>

# To run this code, "api_key" file is needed, having your RIPE Atlas key


from datetime import datetime  
import csv
import time
from ripe.atlas.cousteau import (
  Ping,
  Traceroute,
  AtlasSource,
  AtlasCreateRequest,
  AtlasResultsRequest
)

def get_API_key() -> str:
    """ Return RIPE API KEY by reading it from a file.
    A file, api_key, is required and the file should contain
    the API key in the first line.
    :return key: (str): API key
    """
    with open("api_key", "r") as f:
        key = f.readline()
    return key

def set_ping(target: str, desc: str) -> Ping:
    """Set parameter for ping.
    :param target: (str) ping target, either an url or ip
    :param desc: (str) description of the experiments
    :return ping: (Ping) Ping object
    """
    ping = Ping(af=4, target=target, description=desc)
    return ping

def set_traceroute(target: str, desc: str) -> Traceroute:
    """Set parameter for traceroute
    :param target: (str) ping target, either an url or ip
    :param desc: (str) description of the experiments
    :return traceroute: (Traceroute) Traceroute object
    """
    traceroute = Traceroute(
        af=4,
        target=target,
        description=desc,
        protocol="ICMP",
    )
    return traceroute

def set_src() -> AtlasSource:
    """
    """
    with open('anchorSelection.csv', 'r') as csvinput:
        reader = csv.reader(csvinput)
        header = next(reader)
        probe_id = ""
        i = 0
        for rows in reader:
            probe_id += str(rows[2]) + ","
            i += 1
        probe_id = probe_id[:-1]

    source = AtlasSource(
                type="probes",
                value=probe_id,  #AtlasResultsRequest
                requested=i,
                tags={"include": ["system-ipv4-works"]},
                action="add"
            )

    return source

def run_exp(api_key: str, meas: list, srcs: list) -> (bool, str):
    """ Run Atlas experiments
    :param api_key: (str): API key
    :param meas: (list): list of experiments to run
    :param srcs: (list): list of sources
    :return is_success: (bool): True if the experiment was successful
    :return response: (str): the measurement ID
    """
    atlas_request = AtlasCreateRequest(
        start_time=datetime.utcnow(),
        key=api_key,
        measurements=meas,
        sources=srcs,
        is_oneoff=True
    )
    (is_success, response) = atlas_request.create()
    return (is_success, response)


def get_results(meas_id: str) -> (bool, list):
    """ Get results.
    :param meas_id: (str): measurement id to retrieve its results
    :return is_success: (bool):  True if the experiment was successful
    :return results: (list): results of the measurement
    """
    kwargs = {
        "msm_id": meas_id
    }
    is_success, results = AtlasResultsRequest(**kwargs).create()

    return (is_success, results)


def main():
    atlas_api_key = get_API_key()
    description = "testing"
    f = open('vpn_configs.csv', 'r')
    file = csv.DictReader(f)
    
    target_list = []
    measurement_id_list_ping = {}
    #store all of the IP addresses of the targeted VPN servers
    for col in file:
        target_list.append(col['ip'])
        
    #for every target in the target list
    for target in target_list:

        ping_obj = set_ping(target, description)
        source = set_src()

        time.sleep(20)
        is_exp_success_ping, response = run_exp(atlas_api_key, [ping_obj], [source])

        print(is_exp_success_ping, response, target)
        if is_exp_success_ping:
            id_ping = response['measurements']
            measurement_id_list_ping[str(target)] = str(id_ping)
    
    with open('../csv/measurement_id_ping.csv', 'a') as csvoutput: #replace w with a for other files
        writer = csv.writer(csvoutput)
        # writer = csv.writer(csvoutput, lineterminator='\n')
        # fieldnames = ["measurement id"] writer = csv.writer(csvoutput, fieldnames=fieldnames)
        # writer.writerow(["IP","measurement id"])
        for key in measurement_id_list_ping.keys():
            msm = measurement_id_list_ping[key].replace("[","").replace("]","")
            writer.writerow([key] + [msm])

    f.close()
    
    


if __name__ == "__main__":
    main()

