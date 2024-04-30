#! /usr/bin/python3
# -*- coding: utf-8 -*-

# Retrieve measurements of anchor topology from RIPE.
# Retrieve data on all topology measurements:
#   ping (potentially traceroute) between one anchor and another,
# for the RIPE anchors that are publicly accessible.

import time
import pickle
from datetime import datetime, timedelta
import multiprocessing as mp

from ripe.atlas.cousteau import (
  Probe,
  AtlasRequest,
  AtlasResultsRequest,
  MeasurementRequest
)

parallel = 1
ANCHORS = set()
NOTANCHORS = set()

def retrieve_meas(msm: dict, current_time: datetime, time_window: timedelta) -> dict:
    stime = time.time()
    mesh_pings = {}

    # get anchor info
    url_path = "/api/v2/anchors/?search=" + msm['target']
    # url_path ex:
    # https://atlas.ripe.net//api/v2/anchors/?search=fr-sxb-as8839.anchors.atlas.ripe.net
    request = AtlasRequest(**{"url_path": url_path})
    (is_success, response) = request.get()
    if not is_success:
        print(f"fail to get anchor info: {url_path}")
        return None
    try:
        target_prb_id = response['results'][0]['probe']
        if response['results'][0]['type'] != 'Anchor':
            return None
    except:
        print(response['results'])
        return None

    meas_start_time = datetime.fromtimestamp(msm['start_time']).strftime("%m-%d-%Y")
    group_url_path = msm['group']  # for later: traceroute and http

    key = (target_prb_id, msm['id'], meas_start_time)
    if key not in mesh_pings:
        mesh_pings[key] = {}

    print(f"reading.. measurement id:{msm['id']}, probe id:{target_prb_id}")
    # Anchor mesh measurement data is too big to call with AtlasRequest
    # We need to use AtlasResultsRequest
    filters2 = {"msm_id": msm['id'],
                "start": current_time - time_window,
                "stop": current_time}

    is_success, results = AtlasResultsRequest(**filters2).create()
    # Reference for format: https://atlas.ripe.net/docs/apis/result-format/
    if not is_success:
        print(f"fail to get measurements on: {msm['id']}")
        return None

    for result in results:
        try:
            org_prb_id = result['prb_id']
            if org_prb_id in NOTANCHORS:
                continue
            if org_prb_id not in ANCHORS:
                probe = Probe(id=org_prb_id)
                if not probe.is_anchor:
                    NOTANCHORS.add(org_prb_id)
                    print(f"{org_prb_id} is not anchor! skip!")
                    continue
                ANCHORS.add(org_prb_id)
            if org_prb_id not in mesh_pings[key]:
                mesh_pings[key][org_prb_id] = []
            one_meas = (result['timestamp'], result['min'])
            mesh_pings[key][org_prb_id].append(one_meas)
        except Exception as e:
            print(e, result)
            return None


    time_taken = round(time.time() - stime)
    print(f"finishing.. {time_taken} seconds, meas id:{msm['id']}, {current_time}, probe id:{target_prb_id}")
    if len(mesh_pings[key]) == 0:
        return None
    return mesh_pings

def run_retrieve_meas(args):
    return retrieve_meas(*args)

def main() -> None:
    """
    get all measurements which have tag: anchoring, mesh
    Reference for API:
    https://atlas.ripe.net/docs/apis/rest-api-reference/#measurements
    """
    time_windows = [timedelta(hours=1)]
    for time_window in time_windows:
        print(str(time_window))
        # Set filter to get all anchor mesh measurement for IPv4
        filters = {"tags": ["anchoring", "mesh"],
                   "type": "ping",
                   "af": 4,
                   "status": 2}  # status 2 (ongoing)
        measurements = MeasurementRequest(**filters)
        mesh_pings = {}

        stime = time.time()
        current_time = datetime.now()
        # current_time = datetime(2022, 12, 8, 0, 00)
        str_current_time = current_time.strftime("%m-%d-%Y")
        with mp.Pool(processes=parallel) as pool:

            for result in pool.imap_unordered(run_retrieve_meas,
                                              ((meas, current_time, time_window) for meas in measurements),
                                              chunksize=3):

                if result is not None:
                    mesh_pings.update(result)

        with open("../pickle/mesh_pings_"  + str_current_time + '_' + str(time_window).split(' ')[0] + ".pickle", "wb") as f:
            pickle.dump(mesh_pings, f)

        etime = time.time() - stime
        print(f"total time: {etime}")
        print(f"total measurement count: {measurements.total_count}")



if __name__ == "__main__":
  main()