#! /usr/bin/python3
# -*- coding: utf-8 -*-

## This script is to run greedy algorithm for geodesic

import csv
import time
import random
import pickle
import networkx as nx
from collections import Counter
import pycountry_convert as pc
from geopy.distance import geodesic as GD

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

def load_anchors(fname: str) -> list:
    anchors = []
   
    with open(fname, "rt") as fp:
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


def get_geo_results(fpath: str) -> dict:
    geo_results = {'anchors': [], 'anchors_decision': {}, 'final_decision': {}}
    # { "anchors: [prb_id, ....] // total 780
    #   "anchors_decision": {"vpn_id": {"prb_id": [T/F]}},
    #   "final_decision": {"vpn_id": T/F}
    count = 0
    with open(fpath, "r") as f:
        reader = csv.DictReader(f)
        header = reader.fieldnames
        for prb_id in header[1:-1]:
            geo_results['anchors'].append(int(prb_id))

        for row in reader:
            count += 1
            counting = Counter(list(row.values())[1:-1])
            # check suspicious cases
            total_results = sum(counting.values())
            assert total_results == 780  # "some data is missing!"
            valid_results = 0
            if 'False' in counting:
                valid_results += counting['False']
            if 'True' in counting:
                valid_results += counting['True']
            if valid_results / total_results <= 0.6:
                # print("valid results are only: ",  valid_results/total_results, counting)
                continue
            # record
            geo_results['final_decision'][row["VPN_IP"]] = row['final']
            geo_results['anchors_decision'][row['VPN_IP']] = {}
            for prb_id in header[1:-1]:
                geo_results['anchors_decision'][row['VPN_IP']][int(prb_id)] = row[prb_id]
            assert counting == Counter(list(geo_results['anchors_decision'][row['VPN_IP']].values()))

    print(f"{count - len(geo_results['final_decision'])}/{count} has been removed.")
    print()
    return geo_results


def get_landmarks(fpath: str, anchors_from_exp: list) -> dict:
    abc = {'city': {}, 'country': {}, 'asn': {}, 'continent': {}, 'anchors': []}
    # anchor by category {'city': {city_name: [ ]},
    #                   'country': {cnt_name: []},
    #                   'asn': {asn_num: []},
    #                   'continent': {'continent_name':[]}}
    
    cnt_by_continent = {}
    
    with open(fpath, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if int(row['pid']) not in anchors_from_exp:
                continue
            abc['anchors'].append(int(row['pid']))
            
            if row['city'] not in abc['city']:
                abc['city'][row['city']] = []
            abc['city'][row['city']].append(int(row['pid']))
            
            if row['country'] not in abc['country']:
                abc['country'][row['country']] = []
            abc['country'][row['country']].append(int(row['pid']))
            
            if int(row['asn']) not in abc['asn']:
                abc['asn'][int(row['asn'])] = []
            abc['asn'][int(row['asn'])].append(int(row['pid']))
            
            if row['country'] == 'SX':
                conti_code = 'NA'
            else:
                conti_code = pc.country_alpha2_to_continent_code(row['country'])
            
            conti_name = pc.convert_continent_code_to_continent_name(conti_code)
            if conti_name not in abc['continent']:
                abc['continent'][conti_name] = []
            abc['continent'][conti_name].append(int(row['pid']))
            
            if conti_name not in cnt_by_continent:
                cnt_by_continent[conti_name] = {}
            if row['country'] not in cnt_by_continent[conti_name]:
                cnt_by_continent[conti_name][row['country']] = []
            cnt_by_continent[conti_name][row['country']].append(int(row['pid']))
            # if row['city'] not in cnt_by_continent[conti_name]:
            #     cnt_by_continent[conti_name][row['city']] = []
            # cnt_by_continent[conti_name][row['city']].append(int(row['pid']))
    
    with open("../pickle/country_by_continent.pickle", "wb") as f:
        pickle.dump(cnt_by_continent, f)
    
    for c, v in cnt_by_continent.items():
        print(c, len(v))
    
    return abc

def get_landmarks_meta(fpath: str, anchors_from_exp: list) -> dict:
    lm_meta = {}
    #  {pid: {'city': str, 'country': str, 'asn': str, 'continent': str]

    with open(fpath, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if int(row['pid']) not in anchors_from_exp:
                continue
            row['pid'] = int(row['pid'])
            lm_meta[row['pid']] = {}
            lm_meta[row['pid']]['city'] = row['city']
            lm_meta[row['pid']]['country'] = row['country']
            lm_meta[row['pid']]['asn'] = row['asn']
            if row['country'] == 'SX':
                conti_code = 'NA'
            else:
                conti_code = pc.country_alpha2_to_continent_code(row['country'])
            conti_name = pc.convert_continent_code_to_continent_name(conti_code)
            lm_meta[row['pid']]['continent'] =conti_name
    return lm_meta

def select_starting_anchor_for_vp(fpath_vpconfig: str, fpath_distance: str, anchors_by_cnt: dict, G) -> dict:
    iso3t2 = {}
    # iso2t3 = {}
    with open("../iso3166.csv", "r") as f:
        reader = csv.DictReader(f)
        for r in reader:
            iso3t2[r['ISO_A3']] = r['ISO_A2']
            # iso2t3[r['ISO_A2']] = r['ISO_A3']

    lan_dist = {} #  {iso3: pid: dist}
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
                sorted_lan_dist = sorted(lan_dist[cnt_iso3].items(), key=lambda x: x[1])
                for pid, dm in sorted_lan_dist:
                    edges = G.edges(pid, data=True)
                    if len(edges) != 0:
                        break
                init_anchors[ip] = pid
            else:
                pid = random.choice(anchors_by_cnt[cnt_iso2])
                init_anchors[ip] = pid

    return init_anchors

def analyze_distance(anchors: list, landmarks: Landmark) -> dict:
    # calculate the shortest distance between two anchors
    lm_distances = {}

    no_exp = set()
    for i in range(len(anchors)):
        for j in range(i+1, len(anchors)):
            fi_pid = anchors[i]
            if fi_pid not in landmarks:
                no_exp.add(fi_pid)
                continue
            fi_lon = landmarks[fi_pid][0]
            fi_lat = landmarks[fi_pid][1]
            se_pid = anchors[j]
            if se_pid not in landmarks:
                no_exp.add(se_pid)
                continue
            se_lon = landmarks[se_pid][0]
            se_lat = landmarks[se_pid][1]
            dist = GD((fi_lon, fi_lat), (se_lon, se_lat)).km
            lm_distances[(fi_pid, se_pid)] = dist
        print(f"** {i}/{len(anchors)} done")

    print(no_exp)
    with open("../pickle/lm_dist.pickle", "wb") as fp:
        pickle.dump(lm_distances, fp)

    return lm_distances

def create_graph(lm_distances: dict):
    G = nx.Graph()
    for (fi_pid, se_pid), dist in lm_distances.items():
        G.add_node(fi_pid)
        G.add_node(se_pid)
        G.add_edge(fi_pid, se_pid, weight=dist)
    return G

def _select_prim(G, weights, MAXG, max_strees, is_random100=False, is_feature=False, cname=None):
    """
    Args:
        G:
        weights:
        MAXG:
        max_strees:
        is_feature: True (prioritize unique cluster), False (don't care about cluster)
        cname:

    Returns:

    """
    if is_feature:
        cluster = set()
        geo_results = get_geo_results("../csv/final_result.csv")
        abc = get_landmarks("../csv/anchorSelectionAll.csv", geo_results['anchors'])
        lm_meta = get_landmarks_meta("../csv/anchorSelectionAll.csv", geo_results['anchors'])
        ctotal = len(abc[cname].keys())

    start_index = 2
    if is_random100:
        start_index = 101

        if is_feature:
            for pid in max_strees[100]:
                cluster.add(lm_meta[pid][cname])

    for k in range(start_index, G.number_of_nodes() + 1):
        # find the maximum among these edges
        if is_feature:
            # sort by weight
            if len(cluster) == ctotal:
                selected_node = max(weights, key=weights.get)
                removed_weight = weights.pop(selected_node)
            else:
                sorted_weight = sorted(weights.items(), key=lambda x: x[1], reverse=True)
                selected_node = sorted_weight[0][0]
                for pid, w in sorted_weight:
                    # check if pid's cluster is unique
                    if lm_meta[pid][cname] not in cluster:
                        cluster.add(lm_meta[pid][cname])
                        selected_node = pid
                        # print(f"{pid} is selected!")
                        break
                removed_weight = weights.pop(selected_node)
        else:
            selected_node = max(weights, key=weights.get)
            removed_weight = weights.pop(selected_node)

        # add the chosen edge to the MST;
        MAXG.add_node(selected_node)
        # find edges connecting any vertex with the fringe vertices
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
 
        # G.add_edge((selected_node, start), weight=rtt)
        max_strees[k] = list(MAXG.nodes()).copy()

        if len(weights) == 0:
            break
 
def select_prim(G, option: str, store_fname: str, is_random100=False, is_feature=False, cname=None, start_point_vp={}):
    """
    Args:
        G:
        option: [max_edge, claimed_cnt, random]: which node we will start adding
        store_fname:
        is_feature:
        cname:
        start_point_vp:

    Returns:
    """
    max_strees = {}
    # select a starting node
    #        either (1) a node with maximum weight
    #            or (2) a node in the claimed country of the target
    print(f"start... {option}, {is_feature}, {cname}")
    if option == "max_edge":
        # initialize an empty set of selected nodes and an empty tree.
        max_strees = {}  # {k value: [list of anchors]}
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

        _select_prim(G, weights, MAXG, max_strees, is_random100, is_feature, cname)

        with open(store_fname, "wb") as f:
            pickle.dump(max_strees, f)
        print(max_strees[10])

    elif option == "random":
        max_strees = {}  # {k value: [list of anchors]}
        MAXG = nx.Graph()
        geo_results = get_geo_results("csv/final_result.csv")
        randomly_selected = random.sample(geo_results['anchors'], k=100)
        for k, sn in enumerate(randomly_selected):
            MAXG.add_node(sn)
            # find edges connecting any vertex with the fringe vertices
            weights = {}  # {to_probe: total_weights_from_selected_nodes_to_the_probe}
            for e in G.edges(sn, data=True):
                node = list(e)
                node.remove(sn)
                weights[node[0]] = e[2]['weight']
            max_strees[k+1] = list(MAXG.nodes()).copy()

        _select_prim(G, weights, MAXG, max_strees, is_random100, is_feature, cname)

        with open(store_fname, "wb") as f:
            pickle.dump(max_strees, f)
        print(max_strees[10])

    elif option == "claimed_cnt":
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
            for e in G.edges(spid, data=True):
                node = list(e)
                node.remove(spid)
                weights[node[0]] = e[2]['weight']

            _select_prim(G, weights, MAXG, max_strees, is_random100, is_feature, cname)
            all_mst[vp_id] = max_strees.copy()
            count += 1

        with open(store_fname, 'wb') as fp:
            pickle.dump(all_mst, fp)
    return max_strees



def main() -> None:
    s = time.time()

    # final_result.csv is the results of active geolocation for VPN
    # Note: We are not releasing the data publicly due to challenges
    #       in anonymizing the VPN provider.
    #       Please contact us if you need access.
    active_anchors = load_anchors("../csv/final_result.csv")
    landmarks, anchors_by_cnt = load_landmarks("../csv/anchorSelectionAll.csv")
    # lm_distances = analyze_distance(active_anchors, landmarks)
    with open("../pickle/lm_dist.pickle", "rb") as fp:
        lm_distances = pickle.load(fp)
    G = create_graph(lm_distances)

    ## starting point for each vantage point
    # start_point_vp = select_starting_anchor_for_vp('csv/vpn_configs.csv', 'csv/landmarks-and-distances_pid.csv',
    #                                                anchors_by_cnt, G)
    start_point_vp = {} # this is for the option starting from the claimed country
    # select_prim(G, 'max_edge','pickle/selected_nodes_only_dist_start_max_cluster_cnt.pickle', Fasle, True, 'country', start_point_vp)
    # select_prim(G, 'claimed_cnt','pickle/selected_nodes_only_air_dist_starting_from_claimed_cnt.pickle', Fasle, False, None, start_point_vp)
    # select_prim(G, 'random', 'pickle/selected_nodes_only_dist_start_max_random100_cluster_cnt.pickle', True, True, 'country', start_point_vp)
    select_prim(G, 'max_edge', 'pickle/selected_nodes_dist_s_max.pickle', False, False, None, start_point_vp)
    print(time.time() - s)


if __name__ == "__main__":
    main()
