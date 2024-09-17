from mulgrids import *
from t2data import *



def normalname_match(name_wc, name):
    """ return true if the name_wc (wild cast * supported) match name """
    is_match = True
    for i in xrange(5):
        if name_wc[i] != '*':
            if name_wc[i] != name[i]:
                is_match = False
                break
    return is_match

def toughname_match(name_wc, name):
    """ return true if the name_wc (wild cast * supported) match name """
    from mulgrids import unfix_blockname
    c_name_wc = unfix_blockname(name_wc)
    c_name = unfix_blockname(name)

    is_match = True
    for i in xrange(5):
        if c_name_wc[i] != '*':
            if c_name_wc[i] != c_name[i]:
                is_match = False
                break
    return is_match

# GENER purpose check

def is_upflow(gener,geo,convention='*** 1'):
    b = gener.block
    w = gener.name
    checks = [
        normalname_match(convention,w),
        geo.layer[geo.layer_name(b)].name == geo.layerlist[-1].name,
        gener.type == 'MASS'
        ]
    return all(checks)

def is_heat(gener,geo,convention='*** 2'):
    b = gener.block
    w = gener.name
    checks = [
        normalname_match(convention,w),
        geo.layer[geo.layer_name(b)].name == geo.layerlist[-1].name,
        gener.type == 'HEAT'
        ]
    return all(checks)

def is_upflow_rech(gener,geo,convention='*** 3'):
    b = gener.block
    w = gener.name
    checks = [
        normalname_match(convention,w),
        geo.layer[geo.layer_name(b)].name == geo.layerlist[-1].name,
        gener.type == 'RECH'
        ]
    return all(checks)

def is_side_rech(gener,geo,convention='*****'):
    b = gener.block
    w = gener.name
    checks = [
        normalname_match(convention,w),
        b == w,
        gener.type == 'RECH'
        ]
    return all(checks)

def is_rain(gener,geo,convention='*****'):
    b = gener.block
    w = gener.name
    checks = [
        normalname_match(convention,w),
        geo.layer_name(b) == geo.layerlist[geo.num_layers - geo.column[geo.column_name(b)].num_layers].name,
        gener.type == 'MASS'
        ]
    return all(checks)

def is_spring(gener,geo,convention='SP***'):
    b = gener.block
    w = gener.name
    checks = [
        normalname_match(convention,w),
        gener.type in ['DELG','MASS'],
        ]
    return all(checks)

def check_geners(geners, checks):
    """ geners, a list of t2generators.  checks, a list of functions that
    accepts generator as argument and return True/False, names of functions
    will be used as dict key when returning counts of each function when
    returning True.  A list of partial functions can be in place the list of
    functions. """

    try:
        fnames = [f.__name__ for f in checks]
    except AttributeError:
        fnames = [pf.func.__name__ for pf in checks]

    # set all counter to zero, dict with func names as key
    count = dict([(n,0) for n in fnames])
    count['UNKNOWN'] = 0

    for i,g in enumerate(geners):
        match = []
        for f,t in zip(checks,fnames):
            if f(g):
                count[t] += 1
                match.append(t)
        if len(match) > 1:
            print('WARNING: %s match types: %s' % (g.name,','.join(match)))
        if len(match) == 0:
            count['UNKNOWN'] += 1
            print('WARNING: %s doe not match any type.' % g.name)

    return count

def wai_area_polygon():
    pline = [
        np.array([ 2768202.24117734 , 6270490.54421648]),
        np.array([ 2776545.06074986 , 6276563.022725  ]),
        np.array([ 2777310.95894013 , 6277137.4463677 ]),
        np.array([ 2778049.5036236  , 6277766.57702399]),
        np.array([ 2780784.85430311 , 6280173.68562197]),
        np.array([ 2781988.4086021  , 6281377.23992095]),
        np.array([ 2783629.61900981 , 6294807.81175738]),
        np.array([ 2772524.09525097 , 6296312.25463111]),
        np.array([ 2764454.8107464  , 6291662.15847593]),
        np.array([ 2762567.41877753 , 6281213.11888018]),
        np.array([ 2764865.11334833 , 6272842.94580086]),
        np.array([ 2767436.34298707 , 6270955.553832  ])]
    return pline

def ro_area_polygon():
    pline = [
        np.array([ 2783739.03303699 , 6294671.0442234 ]),
        np.array([ 2781742.22704094 , 6281623.42148211]),
        np.array([ 2785216.12240393 , 6279462.49444529]),
        np.array([ 2787267.63541357 , 6279626.61548606]),
        np.array([ 2788416.48269896 , 6279134.25236375]),
        np.array([ 2795911.34356084 , 6279927.50406081]),
        np.array([ 2790440.64220181 , 6292263.93562543]),
        np.array([ 2784586.99174764 , 6294534.27668943])]
    return pline

def th_area_polygon():
    pline = [
        np.array([ 2788334.42217858 , 6279298.37340452]),
        np.array([ 2795938.69706763 , 6280118.97860838]),
        np.array([ 2797579.90747534 , 6272131.75462419]),
        np.array([ 2794188.07263274 , 6265129.25688463]),
        np.array([ 2789784.15803872 , 6262776.85530024]),
        np.array([ 2778842.75532066 , 6260479.16072945]),
        np.array([ 2771566.72251314 , 6264992.48935065]),
        np.array([ 2768421.0692317  , 6269970.82758737]),
        np.array([ 2778131.56414398 , 6277848.63754438]),
        np.array([ 2781632.81301376 , 6280966.93731903]),
        np.array([ 2784942.58733598 , 6279407.7874317 ]),
        np.array([ 2786747.91878446 , 6279653.96899286]),
        np.array([ 2788115.59412422 , 6279353.08041811])]
    return pline

if __name__ == '__main__':

    geo = mulgrid('gwai41458_09.dat')
    nsdat = t2data('wai41458ns_464.dat')
    prdat = t2data('wai41458pr_464.dat')

    # check these possibilities
    from functools import partial
    g_types = [
    partial(is_rain,geo=geo,convention='*** 0'),
    partial(is_heat,geo=geo,convention='*** 2'),
    partial(is_upflow,geo=geo,convention='*** 1'),
    partial(is_upflow_rech,geo=geo,convention='*** 3'),
    partial(is_side_rech,geo=geo,convention='*****')
    ]

    print('+++++', nsdat.filename)
    count = check_geners(nsdat.generatorlist, g_types)
    for t in sorted(count.keys()):
        print('%20s = %i' % (t,count[t]))
    print('Total # of generators is ', len(nsdat.generatorlist))

    print('+++++', prdat.filename)
    count = check_geners(prdat.generatorlist, g_types)
    for t in sorted(count.keys()):
        print('%20s = %i' % (t,count[t]))
    print('Total # of generators is ', len(prdat.generatorlist))
