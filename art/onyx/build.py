"""Build the City Drive Onyx garage vehicle in Blender 4.3+."""
import math
import sys
from pathlib import Path

import bpy
import bmesh
from mathutils import Vector
from math import sin, cos, pi

OUT = Path(sys.argv[sys.argv.index("--")+1]).resolve()
OUT.mkdir(parents=True, exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.unit_settings.system = 'METRIC'
root = bpy.data.objects.new("Onyx", None)
scene.collection.objects.link(root)


def material(name, color, metal=0, rough=.35, coat=0, emission=0):
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = (*color, 1)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get('Principled BSDF')
    for key, value in {
        'Base Color': (*color, 1), 'Metallic': metal, 'Roughness': rough,
        'Coat Weight': coat, 'Coat Roughness': .18,
        'Emission Color': (*color, 1), 'Emission Strength': emission,
    }.items():
        bsdf.inputs[key].default_value = value
    return mat


paint = material("01 • Satin titanium", (.17,.185,.201), .57,.34,.26)
lip = material("02 • Smoked titanium", (.085,.11,.14), .72,.31)
carbon = material("03 • Twill carbon", (.04,.046,.055), .24,.33,.38)
rubber = material("04 • Tire rubber", (.014,.016,.019), .02,.64)
glass = material("05 • Smoked canopy", (.012,.021,.03), .24,.24,.52)
metal = material("06 • Machined alloy", (.33,.37,.41), .89,.24)
rotor = material("07 • Carbon ceramic", (.18,.19,.20), .53,.42)
black = material("08 • Duct recess", (.012,.016,.019), .1,.78)
cyan = material("09 • Ice cyan trim", (.018,.38,.54), .36,.26,.2,.15)
head = material("10 • LED white", (.71,.88,1), .1,.22,0,3)
tail = material("11 • LED red", (.95,.022,.034), .19,.28,0,2.5)
brake = material("12 • Anodized caliper", (.019,.21,.27), .55,.27)
rim = material("13 • Forged wheel", (.095,.105,.12), .75,.23,.3)

# Baked tile shared by Blender and the exported PBR material.
tile = bpy.data.images.new('carbon-twill', 64,64)
pixels = []
for y in range(64):
    for x in range(64):
        warp = ((x//8+y//8)//2)%2
        thread = x if warp else y
        value = (.18 if warp else .14) + .026*cos(thread*pi/2) + .014*cos((x+y)*pi/8)
        pixels.extend((value,value*1.035,value*1.08,1))
tile.pixels.foreach_set(pixels)
tile.filepath_raw = str(OUT/'carbon-twill.png')
tile.file_format = 'PNG'
tile.save()
tile.pack()
node = carbon.node_tree.nodes.new('ShaderNodeTexImage')
node.image = tile
carbon.node_tree.links.new(node.outputs['Color'],carbon.node_tree.nodes['Principled BSDF'].inputs['Base Color'])


def mesh(name, verts, faces, mat, smooth=True, bevel=0, uv=None):
    data = bpy.data.meshes.new(name)
    data.from_pydata(verts,[],faces)
    data.update()
    obj = bpy.data.objects.new(name,data)
    scene.collection.objects.link(obj)
    obj.parent = root
    data.materials.append(mat)
    if uv:
        layer = data.uv_layers.new()
        for polygon in data.polygons:
            for i in polygon.loop_indices:
                layer.data[i].uv = uv[data.loops[i].vertex_index]
    bm = bmesh.new()
    bm.from_mesh(data)
    bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
    bm.to_mesh(data)
    bm.free()
    for polygon in data.polygons:
        polygon.use_smooth = smooth
    if bevel:
        mod = obj.modifiers.new('Machined edge radius','BEVEL')
        mod.width = bevel
        mod.segments = 3
        mod.affect = 'EDGES'
        mod = obj.modifiers.new('Area weighted normals','WEIGHTED_NORMAL')
        mod.keep_sharp = True
    return obj


def sample(rows, steps):
    """Cubic interpolation over the control cage."""
    result = []
    for i in range(len(rows)-1):
        a,b,c,d = [Vector(rows[j]) for j in (max(0,i-1),i,i+1,min(len(rows)-1,i+2))]
        for k in range(steps):
            t = k/steps
            result.append(.5*((2*b)+(-a+c)*t+(2*a-5*b+4*c-d)*t*t+(-a+3*b-3*c+d)*t*t*t))
    return result+[Vector(rows[-1])]


def loft(name, rows, mat, steps=4):
    rows = list(zip(*(sample(column,steps) for column in zip(*rows))))
    n = len(rows[0])
    verts = [tuple(v) for row in rows for v in row]
    faces = [tuple(reversed(range(n)))]
    for i in range(len(rows)-1):
        for j in range(n):
            k = (j+1)%n
            faces.append((i*n+j,i*n+k,(i+1)*n+k,(i+1)*n+j))
    faces.append(tuple(range(len(verts)-n,len(verts))))
    uv = [(j/n*7,i/(len(rows)-1)*11) for i in range(len(rows)) for j in range(n)]
    return mesh(name,verts,faces,mat,uv=uv)


def crease(object, radians=.42):
    modifier = object.modifiers.new('Preserve panel creases','EDGE_SPLIT')
    modifier.split_angle = radians
    modifier.use_edge_sharp = False
    return object


def plate(name, outline, offset, mat, bevel=.009):
    n = len(outline)
    verts = outline + [tuple(Vector(v)+Vector(offset)) for v in outline]
    faces = [tuple(range(n)),tuple(range(n,2*n))]
    faces.extend((i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n))
    uv = [(v[0]*7+v[2]*3,v[1]*7+v[2]*6) for v in verts]
    return mesh(name,verts,faces,mat,False,bevel,uv)


def line(name, points, size, mat):
    data = bpy.data.curves.new(name,'CURVE')
    data.dimensions = '3D'
    data.resolution_u = 10
    data.bevel_depth = size
    data.bevel_resolution = 3
    data.use_fill_caps = True
    path = data.splines.new('BEZIER')
    path.bezier_points.add(len(points)-1)
    for control, point in zip(path.bezier_points,points):
        control.co = point
        control.handle_left_type = control.handle_right_type = 'AUTO'
    obj = bpy.data.objects.new(name,data)
    scene.collection.objects.link(obj)
    obj.parent = root
    data.materials.append(mat)
    return obj


# Main body panels and side channels share these packaging dimensions.
AXLES = (-1.39,1.39)
TIRE_R = .355
sections = [
    (-2.35,.57,.54,.43),(-2.15,.65,.69,.49),(-1.78,.68,.75,.54),
    (-1.07,.63,.78,.54),(-.53,.63,.84,.54),(.03,.57,.83,.49),
    (.57,.51,.72,.36),(1.02,.41,.56,.25),(1.62,.34,.44,.20),
    (2.07,.32,.34,.17),(2.35,.25,.28,.15)
]
crease(loft('Chiseled center monocoque and nose', [[
    (-w,y,b),(-w,y,z-.13),(-w*.80,y,z-.064),(-w*.34,y,z+.012),
    (-w*.08,y,z+.043),(0,y,z+.049),(w*.08,y,z+.043),(w*.34,y,z+.012),
    (w*.80,y,z-.064),(w,y,z-.13),(w,y,b)
] for y,w,z,b in sections], paint))

fender_stations = [
    (-2.35,.69,.96,.50,.705),(-2.15,.67,1.02,.47,.80),
    (-1.89,.64,1.035,.40,.86),(-1.39,.70,1.04,.744,.916),
    (-.91,.61,.995,.36,.86),(-.59,.57,.97,.32,.79),
    (0,.54,.95,.29,.73),(.54,.57,.965,.24,.73),
    (.89,.61,1.00,.32,.805),(1.39,.67,1.025,.744,.86),
    (1.88,.59,.985,.31,.73),(2.14,.48,.94,.17,.57),
    (2.35,.43,.84,.127,.395)
]
# Dense rows hold circular wheel openings while shoulder sections flow smoothly.
fender_profile = sample(fender_stations,7)
for side in (-1,1):
    S = 'L' if side < 0 else 'R'
    rows = []
    for y,inner,outer,bottom,top in fender_profile:
        distance = min(abs(y-axle) for axle in AXLES)
        arch = .355 + math.sqrt(max(0,.397**2-distance**2))
        if distance < .40:
            bottom = max(.31,arch)
        elif distance < .52:
            bottom = .31 + (.52-distance)/.12 * .045
        span = outer-inner
        points = [(inner,bottom*.72),(inner+.018,top-.22),
                  (inner+span*.38,top-.015),(outer-.079,top),
                  (outer-.036,top-.047),(outer,top-.129),
                  (outer-.011,bottom+.057),(outer-.059,bottom),(inner+.048,bottom*.72)]
        rows.append([(side*x,y,z) for x,z in points])
    crease(loft(f'{S} angular shoulder and wheel arch',rows,paint,1),.35)
    # A dark, inset upper extraction slit follows the angled shoulder.
    plate(f'{S} upper front extraction',[(side*.71,1.83,.742),(side*.856,1.77,.801),
        (side*.904,1.54,.844),(side*.79,1.59,.819)],(0,0,-.028),black,.008)
    plate(f'{S} upper rear extraction',[(side*.685,-1.00,.841),(side*.783,-1.085,.88),
        (side*.827,-1.38,.946),(side*.729,-1.29,.922)],(0,0,-.026),black,.008)
    plate(f'{S} side airfoil',[(side*.50,-.94,.39),(side*.89,-.68,.385),
        (side*.953,-.10,.426),(side*.82,.56,.45),(side*.67,.75,.41)],(0,0,-.05),carbon,.011)

    for axle in AXLES:
        arc = []
        for i in range(15):
            angle = .08 + (pi-.16)*i/14
            y = axle+.401*cos(angle)
            z = .355+.404*sin(angle)
            x = (.997 if axle<0 else .984)+.024*sin(angle)
            arc.append((side*x,y,z))
        line(f'{S} wheel arch liner edge {axle}',arc,.009,lip)

    # The sidepod leaves open air between the sill and raised shoulder.
    plate(f'{S} venturi sill',[(side*.43,-1.00,.145),(side*.985,-1.02,.155),
        (side*.96,.91,.135),(side*.65,1.09,.13),(side*.48,.45,.13)],(0,0,-.054),carbon)
    plate(f'{S} fin at venturi entrance',[(side*.76,.72,.21),(side*.937,.8,.225),
        (side*.91,.52,.55),(side*.69,.28,.55)],(0,.08,.018),lip)
    line(f'{S} cyan sill pinstripe',[(side*.974,-.94,.164),(side*.943,-.1,.156),
        (side*.95,.73,.15),(side*.872,.94,.149)],.009,cyan)
    line(f'{S} door shut line',[(side*.795,-.68,.79),(side*.864,-.43,.755),
        (side*.965,-.24,.58),(side*.965,.32,.56),(side*.929,.67,.666),
        (side*.801,.87,.75)],.004,black)

    plate(f'{S} intake splitter',[(side*.34,1.96,.30),(side*.773,2.20,.39),
        (side*.858,2.295,.17),(side*.446,2.36,.14)],(0,-.17,-.013),carbon)
    plate(f'{S} inlet inner wall',[(side*.345,2.22,.146),(side*.48,2.24,.158),
        (side*.52,2.16,.30),(side*.397,2.0,.31)],(0,-.19,0),lip)
    plate(f'{S} brake duct back',[(side*.46,1.91,.17),(side*.84,1.96,.18),
        (side*.81,1.94,.39),(side*.47,1.9,.32)],(0,-.045,0),black)
    # Projector cassette sits in front of the rising outer fender surface.
    housing = [(side*.762,2.390,.364),(side*.871,2.295,.433),
               (side*.919,2.185,.529),(side*.929,2.073,.625),
               (side*.86,2.093,.649),(side*.825,2.211,.555),
               (side*.758,2.325,.451),(side*.711,2.381,.401)]
    plate(f'{S} chamfered projector cassette',housing,(0,-.041,-.024),black,.014)
    for i in range(3):
        arc = [(side*.766,2.369,.422),(side*.827,2.288,.482),(side*.883,2.195,.557)][i]
        x,y,z = arc
        line(f'{S} lamp optic {i}',[(side*(side*x-.019),y+.018,z+.014),(side*(side*x+.033),y+.012,z-.026)],.014,head)

    plate(f'{S} nose bridge rib',[(side*.287,2.388,.289),(side*.554,2.340,.344),
        (side*.725,2.206,.393),(side*.682,2.195,.440),(side*.504,2.302,.401),
        (side*.278,2.339,.317)],(0,-.095,-.025),paint,.012)

    # Lower hanging aero blade shields the visible inner tire face.
    loft(f'{S} swept inlet upper blade',[
        [(side*.34,2.16,.31),(side*.44,2.16,.345),(side*.74,2.16,.412),(side*.82,2.16,.39)],
        [(side*.373,1.92,.36),(side*.48,1.92,.41),(side*.78,1.92,.49),(side*.86,1.92,.45)],
        [(side*.41,1.68,.38),(side*.51,1.68,.446),(side*.77,1.68,.53),(side*.85,1.68,.49)],
        [(side*.43,1.48,.40),(side*.55,1.48,.47),(side*.73,1.48,.51),(side*.82,1.48,.478)]
    ],carbon)
    for i in range(2):
        x = .56+i*.148
        plate(f'{S} inlet guide vane {i}',[(side*x,2.255,.153),(side*(x+.031),2.214,.345),
            (side*(x+.061),1.91,.40),(side*(x+.021),1.91,.15)],(side*.025,0,0),lip,.007)

    # Formed rear ducts and diffuser straps with open, dark passages.
    # The louvres sit in front of a closed structural bulkhead.
    plate(f'{S} rear buttress shroud',[(side*.44,-2.341,.565),(side*.68,-2.375,.728),
        (side*.92,-2.348,.747),(side*1.017,-2.335,.62),(side*.995,-2.373,.394),
        (side*.876,-2.389,.38),(side*.74,-2.387,.552)],(0,.072,0),paint,.014)
    plate(f'{S} sculpted diffuser tunnel surround',[(side*.165,-2.415,.149),
        (side*.321,-2.428,.355),(side*.54,-2.432,.421),(side*.745,-2.422,.369),
        (side*.982,-2.405,.148),(side*.882,-2.429,.153),(side*.68,-2.447,.303),
        (side*.457,-2.446,.309),(side*.25,-2.441,.15)],(0,.062,0),carbon,.012)
    plate(f'{S} recessed rear outlet',[(side*.519,-2.405,.431),(side*.849,-2.403,.442),
        (side*.913,-2.39,.582),(side*.613,-2.383,.586)],(0,.031,0),black,.010)
    for i in range(4):
        z = .461+i*.029
        line(f'{S} rear outlet louvre {i}',[(side*.616,-2.416,z),(side*.72,-2.42,z+.005),
             (side*.854,-2.413,z+.004)],.007,lip)
    for i in range(3):
        x = side*(.33+i*.255)
        plate(f'{S} diffuser strake {i}',[(x,-2.37,.128),(x,-1.32,.114),
              (x,-1.44,.174),(x,-2.31,.42)],(side*.033,0,0),carbon,.006)
    line(f'{S} lower diffuser highlight',[(side*.18,-2.42,.152),
        (side*.47,-2.42,.206),(side*.76,-2.42,.219),(side*.98,-2.39,.146)],.01,cyan)
    for i in range(2):
        x = side*(.847+i*.102)
        trunk = [(x,-2.384,.387),(x,-2.387,.526),(x,-2.357,.671)]
        line(f'{S} tail lamp recess {i}',trunk,.036,black)
        line(f'{S} vertical tail optic {i}',[(px,py-.028,pz) for px,py,pz in trunk],.014,tail)

# Closed rear fascia spans both wheels and the floor. Air outlets have visible back walls.
rear = [
    (-.98,-2.32,.154),(-1.008,-2.325,.46),(-.937,-2.31,.704),
    (-.68,-2.305,.755),(-.41,-2.34,.722),(0,-2.351,.684),
    (.41,-2.34,.722),(.68,-2.305,.755),(.937,-2.31,.704),
    (1.008,-2.325,.46),(.98,-2.32,.154)
]
plate('Closed rear crash structure',rear,(0,.25,0),black,.014)
plate('Satin center rear keel',[(0,-2.427,.154),(-.225,-2.403,.173),(-.166,-2.413,.456),
      (-.27,-2.398,.624),(0,-2.42,.688),(.27,-2.398,.624),(.166,-2.413,.456),
      (.225,-2.403,.173)],(0,.105,0),lip,.015)
plate('Rear diffuser floor closure',[(-1.01,-2.386,.115),(1.01,-2.386,.115),
      (.95,-1.83,.108),(-.95,-1.83,.108)],(0,0,-.027),carbon,.006)

# Wheel pod and floor shapes leave a line of sight through the side channels.
plate('Carbon undertray', [(-.95,-2.37,.12),(.95,-2.37,.12),
      (.88,-1.6,.10),(.465,-.6,.095),(.47,.99,.087),(.93,2.35,.103),
      (-.93,2.35,.103),(-.47,.99,.087),(-.465,-.6,.095),(-.88,-1.6,.10)],
      (0,0,-.028),carbon)
line('Front cyan splitter perimeter',[(-.89,2.354,.121),(-.67,2.395,.135),(-.32,2.38,.158),
     (0,2.40,.126),(.32,2.38,.158),(.67,2.395,.135),(.89,2.354,.121)],.007,cyan)
line('Nose centerline',[(0,2.265,.303),(0,1.78,.436),(0,1.37,.526),(0,1.043,.577)],.007,cyan)

def canopy_rows(profile, low=.62):
    return [[(-w,y,base),(-w*.97,y,base+(z-base)*.46),(-w*.76,y,base+(z-base)*.82),
             (-w*.47,y,z-.014),(0,y,z),(w*.47,y,z-.014),
             (w*.76,y,base+(z-base)*.82),(w*.97,y,base+(z-base)*.46),(w,y,base),(0,y,low)]
            for y,w,z,base in profile]

profile = [(-1.61,.13,.79,.73),(-1.43,.28,.89,.74),(-1.10,.40,1.055,.759),
           (-.75,.44,1.13,.78),(-.34,.45,1.105,.78),(.03,.415,1.017,.752),
           (.36,.35,.901,.706),(.65,.275,.77,.664),(.86,.15,.657,.619)]
crease(loft('Laminated canopy glazing',canopy_rows(profile),glass,6),.34)
for side in (-1,1):
    line('Canopy satin frame',[(side*w,y,base+.009) for y,w,z,base in profile],.018,lip)
    line('Canopy A pillar',[(side*.29,.56,.699),(side*.34,.38,.788),
         (side*.31,.17,.932),(side*.20,-.03,1.02)],.012,carbon)
    line('Canopy rear rain channel',[(side*.24,-1.48,.818),(side*.39,-1.12,.913),
         (side*.44,-.77,.93),(side*.439,-.39,.896)],.012,lip)
    line('Mirror stanchion',[(side*.43,.12,.78),(side*.57,.142,.812),
         (side*.66,.165,.863)],.017,carbon)
    loft('Shaped mirror shell',[
       [(side*.565,.21,.856),(side*.587,.21,.9),(side*.734,.21,.901),(side*.753,.21,.861)],
       [(side*.561,.12,.849),(side*.577,.12,.913),(side*.724,.12,.916),(side*.775,.12,.855)],
       [(side*.58,.057,.857),(side*.595,.057,.897),(side*.73,.057,.896),(side*.758,.057,.861)]],paint)
    plate('Mirror glass',[(side*.587,.049,.858),(side*.744,.049,.86),(side*.725,.048,.894),
         (side*.596,.049,.897)],(0,.006,0),glass,.004)
    for i in range(5):
        y = -1.93+i*.084
        line('Engine bay louvre',[(side*.20,y,.753+i*.008),(side*.38,y+.045,.769+i*.009),
             (side*.55,y+.057,.748+i*.009)],.014,black)

loft('Roof intake nacelle',[
    [(-.073,-1.2,1.015),(-.05,-1.2,1.11),(.05,-1.2,1.11),(.073,-1.2,1.015)],
    [(-.105,-.89,1.091),(-.092,-.89,1.202),(.092,-.89,1.202),(.105,-.89,1.091)],
    [(-.095,-.69,1.107),(-.092,-.69,1.194),(.092,-.69,1.194),(.095,-.69,1.107)]],carbon)
plate('Roof scoop aperture',[(-.075,-.684,1.133),(.075,-.684,1.133),
    (.075,-.684,1.181),(-.075,-.684,1.181)],(0,-.027,0),black,.003)
for side in (-1,1):
    plate('Swept wing mount',[(side*.39,-2.105,.69),(side*.41,-1.82,.70),
         (side*.66,-1.78,1.205),(side*.58,-2.11,1.209)],(side*.038,0,0),carbon)
    plate('Wing vertical end plate',[(side*1.035,-2.29,1.191),(side*1.04,-1.75,1.213),
         (side*1.039,-1.77,1.32),(side*1.03,-2.28,1.306)],(side*.029,0,0),carbon)
    line('Wing end cyan tip',[(side*1.064,-2.283,1.201),(side*1.062,-2.285,1.308),
         (side*1.064,-2.231,1.322)],.008,cyan)

# Airfoil wraps around its leading and trailing edges.
foil = []
for i in range(25):
    x = -1.053+2.106*i/24
    z = 1.226 + .043*abs(x)
    foil.append([(x,-2.29,z+.022),(x,-2.235,z+.041),(x,-1.92,z+.053),
                 (x,-1.753,z+.009),(x,-1.835,z-.021),(x,-2.16,z-.016)])
loft('Bridge wing airfoil',foil,carbon,1)
line('Wing trailing edge',[(-1.03,-2.291,1.287),(-.53,-2.291,1.268),
     (0,-2.291,1.249),(.53,-2.291,1.268),(1.03,-2.291,1.287)],.008,lip)
line('Central rain light',[(0,-2.405,.417),(0,-2.41,.502),(0,-2.398,.567)],.014,tail)

# Machined wheels, tires, drilled ceramic rotors and independent calipers.
def wheel_lathe(name,x,y,z,profile,mat):
    segments = 64
    verts = [(x+axial,y+r*cos(2*pi*i/segments),z+r*sin(2*pi*i/segments))
             for axial,r in profile for i in range(segments)]
    faces = [(j*segments+i,j*segments+(i+1)%segments,
              ((j+1)%len(profile))*segments+(i+1)%segments,((j+1)%len(profile))*segments+i)
             for j in range(len(profile)) for i in range(segments)]
    return mesh(name,verts,faces,mat)

def dotted_ring(name,x,y,z,rings,mat):
    verts, faces = [], []
    for radius,count,size in rings:
        for i in range(count):
            a = 2*pi*i/count + radius
            start = len(verts)
            verts.extend((x,y+radius*cos(a)+size*cos(2*pi*j/6),
                          z+radius*sin(a)+size*sin(2*pi*j/6)) for j in range(6))
            faces.append(tuple(range(start,start+6)))
    obj = mesh(name,verts,faces,mat,False)
    return obj

for side in (-1,1):
    for y in AXLES:
        rear = y<0
        x = (.867 if rear else .857)*side
        wid = .172 if rear else .153
        z = TIRE_R
        wheel_lathe('Performance tire',x,y,z,[(-wid,.267),(-wid,.308),(-wid*.9,.338),
            (-wid*.65,.351),(-wid*.36,.355),(wid*.36,.355),(wid*.65,.351),
            (wid*.9,.338),(wid,.308),(wid,.267)],rubber)
        wheel_lathe('Forged rim barrel',x,y,z,[(-wid,.255),(wid,.255),(wid+.002,.281),
            (wid*.76,.282),(-wid*.9,.28)],rim)
        wheel_lathe('Diamond cut rim lip',x,y,z,
            [(side*(wid+.003),.265),(side*(wid+.004),.277),
             (side*(wid-.016),.278),(side*(wid-.014),.268)],metal)
        wheel_lathe('Ventilated brake rotor',x,y,z,
            [(side*(wid-.063),.066),(side*(wid-.063),.223),(side*(wid-.079),.223),(side*(wid-.079),.066)],rotor)
        dotted_ring('Rotor drilled pattern',x+side*(wid-.062),y,z,
                    [(.193,24,.006),(.209,28,.0047)],black)
        wheel_lathe('Center lock',x,y,z,[(side*(wid+.021),.047),(side*(wid+.020),.067),
            (side*(wid-.04),.067),(side*(wid-.04),.032),(side*(wid+.021),.032)],metal)
        wheel_lathe('Center lock anodized ring',x,y,z,[(side*(wid+.023),.040),(side*(wid+.023),.051),
            (side*(wid+.018),.051),(side*(wid+.018),.040)],cyan)
        def at(r,a,depth):
            return (x+side*(wid+depth), y+r*cos(a), z+r*sin(a))
        for i in range(9):
            a = 2*pi*i/9
            plate('Tapered forged spoke',[at(.062,a-.10,.013),at(.264,a-.04,-.002),
                at(.268,a+.105,-.002),at(.124,a+.24,.004),at(.063,a+.20,.013)],
                (-side*.027,0,0),rim,.007)
        plate('Brake caliper', [at(.162,.52,-.048),at(.236,.48,-.048),
              at(.24,1.08,-.048),at(.172,1.02,-.048)],(-side*.041,0,0),brake,.017)
        # Inlaid transverse tread on the crown, no separate draw call per groove.
        verts, faces = [], []
        for i in range(40):
            a = 2*pi*i/40
            for band in (-1,1):
                p = len(verts)
                for u,t in [(band*.014,0),(band*wid*.68,.055),(band*wid*.68,.080),(band*.014,.022)]:
                    radius = .356 if abs(u)<.03 else .352
                    verts.append((x+u,y+radius*cos(a+t),z+radius*sin(a+t)))
                faces.append(tuple(range(p,p+4)))
        mesh('Molded directional tread',verts,faces,black,False)

# A pair of recessed, heat-darkened exhaust outlets.
for x in (-.39,.39):
    pipe = wheel_lathe('Exhaust lip',0,0,0,[(-.085,.062),(.08,.062),(.085,.083),(.07,.091),(-.085,.087)],metal)
    pipe.rotation_euler.z = pi/2
    pipe.location = (x,-2.29,.619)
    cap = wheel_lathe('Dark exhaust backwall',0,0,0,[(-.018,.001),(-.018,.062),(.014,.062),(.014,.001)],black)
    cap.rotation_euler.z = pi/2
    cap.location = (x,-2.31,.619)

# Save editable Blender data before adding the temporary rendering rig.
for obj in list(root.children):
    obj.select_set(False)
bpy.context.view_layer.objects.active = root
root.select_set(True)
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'Onyx.blend'))
assert 'FINISHED' in bpy.ops.export_scene.gltf(filepath=str(OUT/'onyx.glb'),
    export_format='GLB',export_apply=True,export_yup=True,export_draco_mesh_compression_enable=False)
print('ONYX_MODEL', sum(o.type=='MESH' for o in root.children), (OUT/'onyx.glb').stat().st_size, flush=True)

if '--render' in sys.argv:
    def point(obj,target):
        obj.rotation_euler = (Vector(target)-obj.location).to_track_quat('-Z','Y').to_euler()
    floor = material('Review floor',(.09,.10,.116),.12,.5)
    bpy.ops.mesh.primitive_plane_add(size=200)
    bpy.context.object.data.materials.append(floor)
    scene.world = bpy.data.worlds.new('Review ambience')
    scene.world.use_nodes = True
    scene.world.node_tree.nodes['Background'].inputs[0].default_value = (.23,.27,.34,1)
    scene.world.node_tree.nodes['Background'].inputs[1].default_value = .42
    for position,power,width,height in [((-2.5,1.7,4.1),850,5,1.7),
        ((2.3,-2.8,3.3),960,5,1.45),((0,4.7,2.5),350,3,2),((0,-5.3,2.5),410,3,2)]:
        data = bpy.data.lights.new('Softbox','AREA')
        data.energy=power
        data.shape='RECTANGLE'
        data.size=width
        data.size_y=height
        obj = bpy.data.objects.new('Softbox',data)
        scene.collection.objects.link(obj)
        obj.location=position
        point(obj,(0,0,.45))
    data=bpy.data.cameras.new('Review camera')
    camera=bpy.data.objects.new('Review camera',data)
    scene.collection.objects.link(camera)
    scene.camera=camera
    scene.render.engine='CYCLES'
    scene.cycles.samples=56
    scene.cycles.use_denoising=False
    scene.render.resolution_x=920
    scene.render.resolution_y=600
    scene.render.resolution_percentage=100
    scene.view_settings.view_transform='AgX'
    for name,xyz,scale in [('front',(0,7,.61),3.35),('rear',(0,-7,.61),3.35),
         ('side',(7,0,.61),5.5),('top',(0,.01,8),5.5),('studio',(4.9,6.6,3),5.7),
         ('rear-studio',(-4.6,-6.6,2.8),5.7)]:
        camera.location=xyz
        point(camera,(0,0,.61))
        if name=='top':
            camera.rotation_euler=(0,0,0)
        data.type='ORTHO'
        data.ortho_scale=scale
        if name in {'side','top'}:
            scene.render.resolution_x=920 if name=='side' else 620
            scene.render.resolution_y=470 if name=='side' else 920
            if name=='top':
                data.ortho_scale=7.8
        else:
            scene.render.resolution_x=920
            scene.render.resolution_y=600
        scene.render.filepath=str(OUT/f'{name}.png')
        bpy.ops.render.render(write_still=True)
