#! /usr/bin/python3
# -*- coding: utf-8 -*-

## This script is to run greedy algorithm for RTT

import csv
import time
import random
import pickle
import networkx as nx
# Type hints
#
from typing import (
    Any,
    AnyStr,
    DefaultDict,
    Dict,
    IO,
    Iterator,
    List,
    MutableMapping,
    NamedTuple,
    Optional,
    Sequence,
    Set,
    Tuple,
)

with open("pickle/lm_dist.pickle", "rb") as f:
    LM_DISTANCE = pickle.load(f)

def load_anchors(fname: str) -> list:
    anchors = []
    with open("csv/final_result.csv", "rt") as fp:
        csv_reader = csv.reader(fp)
        for row in csv_reader:
            for prb_id in row[1:-1]:
                anchors.append(int(prb_id))
            break

    return anchors

Landmark = Dict[str, Any]
def load_landmarks(fname: str) -> (Landmark, dict):
    rv = {}  # {pid(str): (longitude(float), ltitude(float))
    anchors_by_cnt = {} # {country: [list of anchors])
    with open(fname, "rt") as fp:
        rd = csv.DictReader(fp)
        for row in rd:
            pid = int(row['pid'].strip())
            longitude = float(row['longitude'].strip())
            latitude = float(row['latitude'].strip())
            rv[pid] = (latitude, longitude)
            if row['country'] not in anchors_by_cnt:
                anchors_by_cnt[row['country']] = []
            anchors_by_cnt[row['country']].append(int(row['pid']))

    return rv, anchors_by_cnt

def select_starting_anchor_for_vp(fpath_vpconfig: str, fpath_distance: str, anchors_by_cnt: dict, G) -> dict:

    iso3t2 = {}
    # iso2t3 = {}
    with open("../csv/iso3166.csv", "r") as f:
        reader = csv.DictReader(f)
        for r in reader:
            iso3t2[r['ISO_A3']] = r['ISO_A2']
            # iso2t3[r['ISO_A2']] = r['ISO_A3']

    lan_dist = {} #  {iso3: pid: dist}
    # we'll have a dictionary to find anchor that is close to the claimed country
    with open(fpath_distance, "rt") as ft:
        reader = csv.DictReader(ft)
        for r in reader:
            addr = r.pop('addr')
            pid = r.pop('pid')
            lon = r.pop('longitude')
            lan = r.pop('latitude')
            for k, v in r.items():
                if k not in lan_dist:
                    lan_dist[k] = {}
                lan_dist[k][int(pid)] = v
 
    init_anchors = {}  # {vp_ip: pid, ...}
    with open(fpath_vpconfig, "rt") as ft:
        reader = csv.DictReader(ft)
        for r in reader:
            ip = r['ip']
            cnt_iso3 = r['claimed_country_iso3']
            cnt_iso2 = iso3t2[cnt_iso3]
            if cnt_iso2 not in anchors_by_cnt:
                # close_pid = min(lan_dist[cnt_iso3], key=lan_dist[cnt_iso3].get)
                sorted_lan_dist = sorted(lan_dist[cnt_iso3].items(), key=lambda x: x[1])
                for pid, dm in sorted_lan_dist:
                    if G.has_node(pid):
                        edges = G.edges(pid, data=True)
                        if len(edges) != 0:
                            break
                    else:
                        print(pid, dm)
                init_anchors[ip] = pid
            else:
                count = 0
                while True:
                    count += 1
                    print(ip, "inside while")
                    pid = random.choice(anchors_by_cnt[cnt_iso2])
                    if G.has_node(pid):
                        edges = G.edges(pid, data=True)
                        if len(edges) != 0:
                            break

                    if count == 10:
                        sorted_lan_dist = sorted(lan_dist[cnt_iso3].items(), key=lambda x: x[1])
                        for pid, dm in sorted_lan_dist:
                            if G.has_node(pid):
                                edges = G.edges(pid, data=True)
                                if len(edges) != 0:
                                    break
                            else:
                                print(pid, dm)
                        break
                init_anchors[ip] = pid

    return init_anchors

def remove_rtt_faster_than_speed_of_light(all_rtts, org_prb_id, target_prb_id):
    # the file below is created in "analyze_air.py"
    # with open("pickle/lm_dist.pickle", "rb") as f:
    #     lm_distance = pickle.load(f)
    global LM_DISTANCE
    if (org_prb_id, target_prb_id) in LM_DISTANCE:
        dist = LM_DISTANCE[(org_prb_id, target_prb_id)]
    elif (target_prb_id, org_prb_id) in LM_DISTANCE:
        dist = LM_DISTANCE[(target_prb_id, org_prb_id)]
    else:
        return all_rtts

    s = 299.792  # km/ms

    all_rtts = list(set(all_rtts))
    temp2 = all_rtts.copy()
    for r in all_rtts:
        owtt = r / 2  #
        if (dist / owtt) > s:
            temp2.remove(r)
            print(f"delete rtt {r}, distance {dist}")
    all_rtts = temp2.copy()
    return all_rtts

def create_graph(anchors, fpath_pings, fpath_graph):
    print(f"Reading... {fpath_pings}")
    with open(fpath_pings, "rb") as f:
        meas_pings = pickle.load(f)
    # meas_pings: {(target_prd_id, msm_id, meas_start_time):
    #                   {org_prb_id:  [(timestamp, minimum_rtt)]}}
    print(f"Done reading... {fpath_pings}")
    meas_pings_min = {}
    _count_removed = 0
    _count_kept = 0
    _anchors_with_no_rtt = set()
    for key in meas_pings:
        meas_pings_min[key] = {}
        for org_prb_id, all_meas in meas_pings[key].items():
            all_rtt = [i[1] for i in all_meas if i[1] > 0]
            # remove all rtts that are faster than speed of light
            all_rtt = remove_rtt_faster_than_speed_of_light(all_rtt, org_prb_id, key[0])
            if len(all_rtt) != 0:
                meas_pings_min[key][org_prb_id] = min(all_rtt)
                _count_kept += 1
            else:
                meas_pings_min[key][org_prb_id] = -1
                _count_removed += 1
                _anchors_with_no_rtt.add(key[0])

    print(f"count_kept: {_count_kept}, count_removed: {_count_removed}")
    print(f"anchors removed (no rtt left): {_anchors_with_no_rtt}")

    # create an empty graph: start creating
    G = nx.Graph()
    DG = nx.DiGraph()

    for (target_prb_id, msm_id, start_date), origins in meas_pings_min.items():
        assert (type(target_prb_id) == int) and (type(list(origins.keys())[0]))

        G.add_node(target_prb_id)
        DG.add_node(target_prb_id)

        for origin_prb_id, rtt in origins.items():
            G.add_node(origin_prb_id)
            DG.add_node(origin_prb_id)

            # Let's give a range for reasonable RTT values
            if rtt == -1:
                continue
            edge = (origin_prb_id, target_prb_id)
            if not G.has_edge(*edge):
                G.add_edge(*edge, weight=rtt)
            else:
                if rtt < G.edges[origin_prb_id, target_prb_id]['weight']:
                    G.edges[origin_prb_id, target_prb_id]['weight'] = rtt

            if not DG.has_edge(*edge):
                DG.add_edge(*edge, weight=rtt)
            else:
                if rtt < DG[origin_prb_id][target_prb_id]['weight']:
                    DG[origin_prb_id][target_prb_id]['weight'] = rtt

    pickle.dump(G, open(fpath_graph, 'wb'))


def _select_prim(G, weights, MAXG, max_strees):
    for k in range(2, G.number_of_nodes() + 1):
        # find the maximum among these edges
        selected_node = max(weights, key=weights.get)
        removed_weight = weights.pop(selected_node)

        # add the chosen edge to the MST;
        MAXG.add_node(selected_node)
        # step2: find edges connecting any vertex with the fringe vertices
        for e in G.edges(selected_node, data=True):
            current_nodes = {e[0], e[1]}
            if len(current_nodes - set(MAXG.nodes())) == 0:
                # remove duplication; we already have this edge in our selection
                continue
            current_nodes.remove(selected_node)
            node = list(current_nodes)[0]
            if node not in weights:
                weights[node] = 0
            weights[node] += e[2]['weight']

        # add the chosen edge to the MST;
        max_strees[k] = list(MAXG.nodes()).copy()

        if len(weights) == 0:
            break

def select_prim(G, option: str, fpath, start_point_vp={}):
    print(f"start prim: {option}, {fpath}")
    #  select a starting node
    #        either (1) a node with maximum weight
    #            or (2) a node in the claimed country of the target
    if option == "max_edge":
        max_strees = {} # {k value: [list of anchors]}
        #  initialize an empty set of selected nodes and an empty tree.
        MAXG = nx.Graph()
        max_edge = max(dict(G.edges).items(), key=lambda x: x[1]['weight'])
        starting_node = random.choice(max_edge[0])
        MAXG.add_node(starting_node)

        # find edges connecting any vertex with the fringe vertices
        weights = {}  # {to_probe: total_weights_from_selected_nodes_to_the_probe}
        for e in G.edges(starting_node, data=True):
            node = list(e)
            node.remove(starting_node)
            weights[node[0]] = e[2]['weight']

        _select_prim(G, weights, MAXG, max_strees)

        with open(fpath, "wb") as f:
            pickle.dump(max_strees, f)

    elif option == "claimed_cnt":
        print("start ... claimed_cnt")
        all_mst = {}
        count = 1
        for vp_id, spid in start_point_vp.items():
            print(f'{count}/{len(start_point_vp)}')
            # initialize an empty set of selected nodes and an empty tree.
            max_strees = {}  # {k value: [list of anchors]}
            MAXG = nx.Graph()
            MAXG.add_node(spid)
            # find edges connecting any vertex with the fringe vertices
            weights = {}  # {to_probe: total_weights_from_selected_nodes_to_the_probe}
            print(vp_id, spid)
            for e in G.edges(spid, data=True):
                node = list(e)
                node.remove(spid)
                weights[node[0]] = e[2]['weight']

            _select_prim(G, weights, MAXG, max_strees)
            all_mst[vp_id] = max_strees.copy()
            count += 1
            print(all_mst[vp_id])

        with open(fpath, 'wb') as fp:
            pickle.dump(all_mst, fp)


def main() -> None:
    s = time.time()
    active_anchors = load_anchors("../csv/final_result.csv")
    # active_anchors: [pid, ... ]
    landmarks, anchors_by_cnt = load_landmarks("csv/anchorSelectionAll.csv")
    # landmarks: {pid(str): (longitude(float), ltitude(float))
    # anchors_by_cnt: {country: [list of anchors])

    fpath_meas = 'mesh_pings_12-08-2022_1:00:00.pickle'
    fpath_graph = 'pickle/ugraph_meas_1h_12-08.pickle'
    create_graph(active_anchors, fpath_meas, fpath_graph)

    G = pickle.load(open(fpath_graph, 'rb'))

    # [diff starting point]
    start_point_vp = {} # this is for the option starting from the claimed country
    start_point_vp = select_starting_anchor_for_vp('csv/vpn_configs.csv', 'csv/landmarks-and-distances_pid.csv',
                                                   anchors_by_cnt, G)
    # select_prim(G, 'claimed_cnt', ""pickle/selected_nodes_only_rtt_starting_from_claimed_cnt.pickle"", start_point_vp)
    # select_prim(G, 'max_edge', "pickle/selected_nodes_only_rtt.pickle", start_point_vp)
    # select_prim(G, 'max_edge', "pickle/selected_nodes_only_owtt_removed.pickle", start_point_vp)
    # select_prim(G, 'max_edge', "pickle/selected_nodes_only_1h.pickle", start_point_vp)
    # select_prim(G, 'max_edge', "pickle/selected_nodes_rtt_s_max_1h_12-08.pickle", start_point_vp)
    select_prim(G, 'claimed_cnt', "pickle/selected_nodes_rtt_s_claimed_1h_12-08.pickle", start_point_vp)

    # G = pickle.load(open('pickle/new_undirect_graph_meas_pings.pickle', 'rb'))
    # nodes = set(list(G.nodes))
    # print(set(list(G.nodes)) - set(anchors))
    # T = nx.maximum_spanning_tree(G, algorithm="prim")
    # print('start')
    # draw_plotly_obj(T) ß
    print(time.time() - s)
    pass


if __name__ == "__main__":
    main()