def parse_aspath(dump):
    dump1 = dump.split('|')
    aspath = dump1[6]
    for i in range(len(aspath)):
        aspath[i] = int(aspath[i])
    return aspath

print(parse_aspath("TABLE_DUMP|1130191746|B|144.228.241.81|1239|128.186.0.0/16|1239 2914 174 11096 2553|IGP|144.228.241.81|0|-2|1239:321 1239:1000 1239:1011|NAG||"))