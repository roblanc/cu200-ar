"""Build a procedural 'control unit' GLB with a baked explode/reassemble loop.
Pure Python, no deps. Units: metres. Y up."""
import json, struct, math, sys

OUT = sys.argv[1]

# ---------- buffers ----------
bin_data = bytearray()
accessors, buffer_views, meshes, nodes, materials = [], [], [], [], []

def pad4():
    while len(bin_data) % 4:
        bin_data.append(0)

def add_view(data: bytes, target=None):
    pad4()
    off = len(bin_data)
    bin_data.extend(data)
    v = {"buffer": 0, "byteOffset": off, "byteLength": len(data)}
    if target: v["target"] = target
    buffer_views.append(v)
    return len(buffer_views) - 1

def add_accessor(values, ctype, typ, target=None, minmax=False):
    if ctype == 5126:
        flat = [c for v in values for c in (v if isinstance(v, (list, tuple)) else [v])]
        data = struct.pack(f"<{len(flat)}f", *flat)
    else:
        data = struct.pack(f"<{len(values)}H", *values)
    bv = add_view(data, target)
    a = {"bufferView": bv, "componentType": ctype, "count": len(values), "type": typ}
    if minmax:
        n = len(values[0]) if isinstance(values[0], (list, tuple)) else 1
        cols = [[(v[i] if n > 1 else v) for v in values] for i in range(n)]
        a["min"] = [min(c) for c in cols]
        a["max"] = [max(c) for c in cols]
    accessors.append(a)
    return len(accessors) - 1

def material(name, rgb, metal=0.1, rough=0.6, emissive=None):
    m = {"name": name, "doubleSided": True, "pbrMetallicRoughness": {
        "baseColorFactor": [*rgb, 1.0], "metallicFactor": metal, "roughnessFactor": rough}}
    if emissive: m["emissiveFactor"] = emissive
    materials.append(m)
    return len(materials) - 1

# ---------- geometry ----------
def box(sx, sy, sz, cx=0, cy=0, cz=0):
    hx, hy, hz = sx / 2, sy / 2, sz / 2
    faces = [((1,0,0), [(hx,-hy,-hz),(hx,hy,-hz),(hx,hy,hz),(hx,-hy,hz)]),
             ((-1,0,0),[(-hx,-hy,hz),(-hx,hy,hz),(-hx,hy,-hz),(-hx,-hy,-hz)]),
             ((0,1,0), [(-hx,hy,-hz),(-hx,hy,hz),(hx,hy,hz),(hx,hy,-hz)]),
             ((0,-1,0),[(-hx,-hy,hz),(-hx,-hy,-hz),(hx,-hy,-hz),(hx,-hy,hz)]),
             ((0,0,1), [(-hx,-hy,hz),(hx,-hy,hz),(hx,hy,hz),(-hx,hy,hz)]),
             ((0,0,-1),[(hx,-hy,-hz),(-hx,-hy,-hz),(-hx,hy,-hz),(hx,hy,-hz)])]
    P, N, I = [], [], []
    for n, quad in faces:
        b = len(P)
        for p in quad:
            P.append((p[0]+cx, p[1]+cy, p[2]+cz)); N.append(n)
        I += [b, b+1, b+2, b, b+2, b+3]
    return P, N, I

def cylinder(r, h, axis="y", cx=0, cy=0, cz=0, seg=28):
    P, N, I = [], [], []
    def place(x, y, z):  # local y = axis
        if axis == "y": return (x, y, z)
        if axis == "x": return (y, x, z)
        return (x, z, y)
    hh = h / 2
    for i in range(seg):
        a0, a1 = 2*math.pi*i/seg, 2*math.pi*(i+1)/seg
        c0, s0, c1, s1 = math.cos(a0), math.sin(a0), math.cos(a1), math.sin(a1)
        b = len(P)
        for (x, y, z), n in [((r*c0,-hh,r*s0),(c0,0,s0)),((r*c1,-hh,r*s1),(c1,0,s1)),
                             ((r*c1, hh,r*s1),(c1,0,s1)),((r*c0, hh,r*s0),(c0,0,s0))]:
            P.append(place(x, y, z)); N.append(place(*n))
        I += [b, b+2, b+1, b, b+3, b+2]
        for yy, ny in [(hh, 1), (-hh, -1)]:
            b = len(P)
            for x, z in [(0, 0), (r*c0, r*s0), (r*c1, r*s1)]:
                P.append(place(x, yy, z)); N.append(place(0, ny, 0))
            I += [b, b+2, b+1] if ny > 0 else [b, b+1, b+2]
    P = [(p[0]+cx, p[1]+cy, p[2]+cz) for p in P]
    return P, N, I

def rot_x(geo, ang):
    P, N, I = geo
    c, s = math.cos(ang), math.sin(ang)
    r = lambda v: (v[0], v[1]*c - v[2]*s, v[1]*s + v[2]*c)
    return [r(p) for p in P], [r(n) for n in N], I

def merge(*geos):
    P, N, I = [], [], []
    for g in geos:
        b = len(P); P += g[0]; N += g[1]; I += [i + b for i in g[2]]
    return P, N, I

def mesh(name, parts):
    """parts: list of (geo, material_index)"""
    prims = []
    for geo, mat in parts:
        P, N, I = geo
        prims.append({"attributes": {
            "POSITION": add_accessor(P, 5126, "VEC3", 34962, minmax=True),
            "NORMAL": add_accessor(N, 5126, "VEC3", 34962)},
            "indices": add_accessor(I, 5123, "SCALAR", 34963), "material": mat})
    meshes.append({"name": name, "primitives": prims})
    return len(meshes) - 1

def node(name, mesh_idx=None, t=(0, 0, 0), children=None):
    n = {"name": name, "translation": list(t)}
    if mesh_idx is not None: n["mesh"] = mesh_idx
    if children: n["children"] = children
    nodes.append(n)
    return len(nodes) - 1

# ---------- materials ----------
M_CHASSIS = material("Chassis graphite", (0.16, 0.18, 0.21), 0.6, 0.45)
M_COVER   = material("Cover safety orange", (0.95, 0.42, 0.10), 0.2, 0.4)
M_PCB     = material("PCB solder mask", (0.05, 0.38, 0.22), 0.0, 0.5)
M_CHIP    = material("IC package", (0.06, 0.06, 0.07), 0.1, 0.35)
M_ALU     = material("Anodised aluminium", (0.78, 0.80, 0.83), 0.9, 0.3)
M_PSU     = material("PSU housing", (0.74, 0.76, 0.79), 0.85, 0.35)
M_COPPER  = material("Copper", (0.85, 0.50, 0.30), 0.9, 0.35)
M_FAN     = material("Fan polymer", (0.10, 0.11, 0.13), 0.0, 0.6)
M_SCREW   = material("Steel screw", (0.70, 0.72, 0.75), 1.0, 0.25)
M_PANEL   = material("Front panel", (0.22, 0.25, 0.29), 0.4, 0.5)
M_LED_G   = material("LED green", (0.2, 1.0, 0.4), 0, 0.3, emissive=[0.2, 1.0, 0.4])
M_LED_A   = material("LED amber", (1.0, 0.65, 0.1), 0, 0.3, emissive=[1.0, 0.65, 0.1])
M_CAP     = material("Capacitor", (0.15, 0.25, 0.55), 0.3, 0.4)

# Case outer: x 0.48, z 0.34, height 0.14
W, D = 0.48, 0.34
T = 0.008

# Chassis (stays put)
chassis = mesh("Chassis", [(merge(
    box(W, T, D, cy=T/2),
    box(T, 0.12, D, cx=-W/2+T/2, cy=0.06),
    box(T, 0.12, D, cx=W/2-T/2, cy=0.06),
    box(W, 0.12, T, cz=-D/2+T/2, cy=0.06),
    *[box(0.03, 0.01, 0.03, cx=x, cy=T+0.005, cz=z) for x in (-0.15, 0.06) for z in (-0.1, 0.1)],  # standoffs
), M_CHASSIS)])

# PCB at y = 0.022 (top of standoffs), centred x=-0.045
PCB_Y = 0.024
caps = merge(*[cylinder(0.008, 0.024, cx=x, cy=0.012+0.004, cz=z) for x, z in
               [(-0.13, -0.08), (-0.11, -0.08), (-0.09, -0.08), (0.04, 0.08), (0.06, 0.08)]])
chips = merge(box(0.055, 0.006, 0.055, cy=0.007),                       # CPU under heatsink
              box(0.03, 0.005, 0.02, cx=-0.10, cy=0.0065, cz=0.06),
              box(0.03, 0.005, 0.02, cx=-0.10, cy=0.0065, cz=0.03),
              box(0.02, 0.004, 0.06, cx=0.07, cy=0.006, cz=-0.05))
pins = merge(*[box(0.004, 0.006, 0.004, cx=-0.155 + i*0.008, cy=0.007, cz=0.105) for i in range(10)])
pcb = mesh("PCB", [(box(0.27, 0.008, 0.25), M_PCB), (chips, M_CHIP), (caps, M_CAP), (pins, M_COPPER)])

# Heatsink sits on CPU
fins = merge(*[box(0.003, 0.034, 0.06, cx=-0.026 + i*0.0074, cy=0.006+0.017) for i in range(8)])
heatsink = mesh("Heatsink", [(merge(box(0.062, 0.006, 0.062, cy=0.003), fins), M_ALU)])

# PSU
psu_vents = merge(*[box(0.07, 0.002, 0.006, cy=0.041, cz=-0.05 + i*0.016) for i in range(7)])
psu = mesh("PSU", [(box(0.10, 0.08, 0.17), M_PSU), (psu_vents, M_CHIP)])

# Fan (frame + blades separate so blades can spin), axis = x
frame = merge(box(0.02, 0.012, 0.11, cy=0.049), box(0.02, 0.012, 0.11, cy=-0.049),
              box(0.02, 0.11, 0.012, cz=0.049), box(0.02, 0.11, 0.012, cz=-0.049),
              box(0.004, 0.10, 0.004), box(0.004, 0.004, 0.10))
fan_frame = mesh("Fan frame", [(frame, M_FAN)])
blades = merge(cylinder(0.016, 0.018, axis="x"),
               *[rot_x(box(0.006, 0.034, 0.016, cy=0.032), k * 2*math.pi/7 + 0.3) for k in range(7)])
fan_blades = mesh("Fan blades", [(blades, M_FAN)])

# Front panel
leds = [(cylinder(0.005, 0.006, axis="z", cx=0.12 + i*0.022, cy=0.09, cz=0.006), M_LED_G if i < 2 else M_LED_A)
        for i in range(3)]
panel = mesh("Front panel", [(box(W, 0.13, 0.012, cy=0.065), M_PANEL),
                              (box(0.12, 0.03, 0.004, cx=-0.14, cy=0.065, cz=0.007), M_CHIP), *leds])

# Cover
cover = mesh("Cover", [(merge(box(W + 0.006, 0.01, D + 0.006),
                              box(W + 0.006, 0.03, 0.006, cy=-0.02, cz=-D/2), # rear lip
                              ), M_COVER)])
screw_geo = merge(cylinder(0.009, 0.004, cy=0.002), box(0.012, 0.0015, 0.002, cy=0.0045),
                  cylinder(0.003, 0.03, cy=-0.015))
screw = mesh("Screw", [(screw_geo, M_SCREW)])

# ---------- nodes (rest positions) ----------
COVER_Y = 0.135
rest = {}
def part(name, m, t, children=None):
    i = node(name, m, t, children); rest[name] = (i, t); return i

blades_n = node("FanBlades", fan_blades, (0, 0, 0))
parts = [
    node("Chassis", chassis),
    part("PCB", pcb, (-0.045, PCB_Y, 0)),
    part("Heatsink", heatsink, (-0.045, PCB_Y + 0.004 + 0.010, 0)),
    part("PSU", psu, (0.17, T + 0.04, 0)),
    part("Fan", fan_frame, (-W/2 + T + 0.012, 0.068, 0), [blades_n]),
    part("FrontPanel", panel, (0, 0, D/2 - 0.006)),
    part("Cover", cover, (0, COVER_Y, 0)),
]
screw_pos = [(-0.215, 0.145), (0.215, 0.145), (-0.215, -0.145), (0.215, -0.145)]
for k, (x, z) in enumerate(screw_pos):
    parts.append(part(f"Screw{k+1}", screw, (x, COVER_Y + 0.005, z)))
root = node("ControlUnit_CU200", None, (0, 0, 0), parts)

# ---------- animation ----------
# Each part: (start_s, end_s, waypoints relative to rest). Reassembly mirrors it in reverse order.
CYCLE = 7.0
plan = {
    "Screw1": (0.8, 1.3, [(0, 0, 0), (0, 0.40, 0)]),
    "Screw2": (0.85, 1.35, [(0, 0, 0), (0, 0.40, 0)]),
    "Screw3": (0.9, 1.4, [(0, 0, 0), (0, 0.40, 0)]),
    "Screw4": (0.95, 1.45, [(0, 0, 0), (0, 0.40, 0)]),
    "Cover": (1.2, 1.9, [(0, 0, 0), (0, 0.29, 0)]),
    "FrontPanel": (1.5, 2.1, [(0, 0, 0), (0, 0, 0.16)]),
    "Heatsink": (1.7, 2.3, [(0, 0, 0), (0, 0.21, 0)]),
    "PCB": (1.85, 2.45, [(0, 0, 0), (0, 0.11, 0)]),
    "Fan": (1.6, 2.4, [(0, 0, 0), (0, 0.15, 0), (-0.17, 0.15, 0)]),
    "PSU": (1.7, 2.5, [(0, 0, 0), (0, 0.13, 0), (0.17, 0.13, 0)]),
}
EXPLODE_END = 2.6     # fully exploded
HOLD_END = 4.0        # start reassembling
# reassembly time t' maps back: t_explode = EXPLODE_END - (t - HOLD_END) * (1.8/1.6) ... simple mirror
def mirrored(t):
    if t <= EXPLODE_END: return t
    if t <= HOLD_END: return EXPLODE_END
    back = (t - HOLD_END) * (1.8 / 1.6)   # reassemble in 1.6s, covering the 1.8s explode window
    return max(0.8, EXPLODE_END - back) if t < HOLD_END + 1.6 else 0.0

def ease(x): return x*x*(3 - 2*x)

def path_at(wps, u):
    if len(wps) == 2:
        a, b = wps; return tuple(a[i] + (b[i]-a[i])*ease(u) for i in range(3))
    # two-leg: first leg 0..0.5, second 0.5..1
    if u < 0.5:
        return path_at(wps[:2], u / 0.5)
    return path_at(wps[1:], (u - 0.5) / 0.5)

FPS = 30
times = [round(i / FPS, 5) for i in range(int(CYCLE * FPS) + 1)]
time_acc = add_accessor(times, 5126, "SCALAR", minmax=True)
samplers, channels = [], []
for name, (s, e, wps) in plan.items():
    idx, r = rest[name]
    vals = []
    for t in times:
        tm = mirrored(t)
        u = 0 if tm <= s else 1 if tm >= e else (tm - s) / (e - s)
        off = path_at(wps, u)
        vals.append(tuple(r[i] + off[i] for i in range(3)))
    samplers.append({"input": time_acc, "output": add_accessor(vals, 5126, "VEC3"), "interpolation": "LINEAR"})
    channels.append({"sampler": len(samplers)-1, "target": {"node": idx, "path": "translation"}})

# Fan blade spin: 2 turns per cycle, faster while assembled
quats = []
for t in times:
    ang = 2 * math.pi * 6 * t / CYCLE
    quats.append((math.sin(ang/2), 0.0, 0.0, math.cos(ang/2)))
samplers.append({"input": time_acc, "output": add_accessor(quats, 5126, "VEC4"), "interpolation": "LINEAR"})
channels.append({"sampler": len(samplers)-1, "target": {"node": blades_n, "path": "rotation"}})

gltf = {
    "asset": {"version": "2.0", "generator": "cu200-demo"},
    "scene": 0, "scenes": [{"name": "Scene", "nodes": [root]}],
    "nodes": nodes, "meshes": meshes, "materials": materials,
    "accessors": accessors, "bufferViews": buffer_views,
    "animations": [{"name": "Explode", "samplers": samplers, "channels": channels}],
}
pad4()
gltf["buffers"] = [{"byteLength": len(bin_data)}]
js = json.dumps(gltf, separators=(",", ":")).encode()
js += b" " * ((4 - len(js) % 4) % 4)
total = 12 + 8 + len(js) + 8 + len(bin_data)
with open(OUT, "wb") as f:
    f.write(struct.pack("<III", 0x46546C67, 2, total))
    f.write(struct.pack("<II", len(js), 0x4E4F534A)); f.write(js)
    f.write(struct.pack("<II", len(bin_data), 0x004E4942)); f.write(bin_data)
print("wrote", OUT, total, "bytes;", len(nodes), "nodes,", len(meshes), "meshes")
