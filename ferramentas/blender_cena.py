"""Roda DENTRO do Blender (chamado por ferramentas/renderizar_glb.py): GLB → cena com céu e sol → PNG pelo Cycles.

    blender -b --factory-startup --python ferramentas/blender_cena.py -- in.glb out.png largura altura amostras vista fundo
"""
import math
import sys

import bpy  # noqa: só existe dentro do Blender
from mathutils import Vector

glb, png, larg, alt, amostras, vista, fundo, norte = sys.argv[sys.argv.index("--") + 1:]
larg, alt, amostras = int(larg), int(alt), int(amostras)

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=glb)
cena = bpy.context.scene
objs = [o for o in cena.objects if o.type == "MESH"]
if not objs:
    raise SystemExit("o GLB não tem malhas")

# caixa do modelo (no Blender, Z para cima; o importador de glTF já converte o Y para cima do arquivo)
cantos = [o.matrix_world @ Vector(c) for o in objs for c in o.bound_box]
mn = Vector((min(c.x for c in cantos), min(c.y for c in cantos), min(c.z for c in cantos)))
mx = Vector((max(c.x for c in cantos), max(c.y for c in cantos), max(c.z for c in cantos)))
centro, raio = (mn + mx) / 2, max((mx - mn).length / 2, 1.0)

# luz de céu suave; sol de apresentação (mesma direção da vista 3D do navegador)
mundo = bpy.data.worlds.new("Physis")
cena.world = mundo
mundo.use_nodes = True
bg = mundo.node_tree.nodes["Background"]
bg.inputs[0].default_value = (1.0, 1.0, 1.0, 1.0)
bg.inputs[1].default_value = 0.8
cena.render.film_transparent = True
sol = bpy.data.objects.new("Sol", bpy.data.lights.new("Sol", type="SUN"))
sol.data.energy = 3.5
sol.data.angle = math.radians(2.0)
sol.rotation_euler = (math.radians(50), 0, math.radians(35))
cena.collection.objects.link(sol)

# câmera: mesmas vistas da physis-3d.js (azimute, elevação)
az, el = {"iso": (0.8, 0.6), "planta": (0.0, 1.5), "frente": (0.0, 0.3), "lado": (math.pi / 2, 0.3)}[vista]
cam = bpy.data.objects.new("Camera", bpy.data.cameras.new("Camera"))
cena.collection.objects.link(cam)
cena.camera = cam
cam.data.lens = 50
d = raio * 2.4
cam.location = centro + Vector((d * math.cos(el) * math.sin(az), -d * math.cos(el) * math.cos(az), d * math.sin(el)))
cam.rotation_euler = (centro - cam.location).to_track_quat("-Z", "Y").to_euler()
cam.data.clip_end = raio * 50

# enquadramento pelos vértices do modelo (amostra), como na vista do navegador: centro do desenho no centro da imagem e
# o modelo ocupando ~85% do quadro
from bpy_extras.object_utils import world_to_camera_view

cena.render.resolution_x, cena.render.resolution_y = larg, alt
bpy.context.view_layer.update()   # posições atualizadas (a seta do norte acabou de entrar na cena)
amostra = []
for o in objs:
    vs = o.data.vertices
    passo = max(1, len(vs) // 400)
    amostra += [o.matrix_world @ vs[i].co for i in range(0, len(vs), passo)]
direcao = (centro - cam.location).normalized()
for _ in range(6):
    bpy.context.view_layer.update()
    pts = [world_to_camera_view(cena, cam, v) for v in amostra]
    pts = [p for p in pts if p.z > 0]
    if not pts:
        break
    u0, u1 = min(p.x for p in pts), max(p.x for p in pts)
    v0, v1 = min(p.y for p in pts), max(p.y for p in pts)
    dist = (centro - cam.location).length
    m = max(u1 - u0, v1 - v0)
    direita = cam.matrix_world.to_3x3() @ Vector((1, 0, 0))
    cima = cam.matrix_world.to_3x3() @ Vector((0, 1, 0))
    # largura visível na distância do alvo (lente 50 mm, sensor 36 mm, ajuste pela maior dimensão)
    vis = dist * cam.data.sensor_width / cam.data.lens
    escala_v = alt / larg if larg >= alt else 1.0
    deslocar = direita * ((u0 + u1) / 2 - 0.5) * vis * (1 if larg >= alt else larg / alt) + cima * ((v0 + v1) / 2 - 0.5) * vis * escala_v
    centro = centro + deslocar
    cam.location = cam.location + deslocar
    nova = dist * (m / 0.85) ** 0.8
    cam.location = centro - direcao * nova

cena.render.engine = "CYCLES"
cena.cycles.samples = amostras
cena.cycles.use_denoising = True
cena.render.resolution_x, cena.render.resolution_y, cena.render.resolution_percentage = larg, alt, 100
try:
    cena.view_settings.view_transform = "AgX"      # Blender 4 e 5
except TypeError:
    cena.view_settings.view_transform = "Filmic"   # Blender 3
cena.render.image_settings.file_format = "PNG"
cena.render.image_settings.color_mode = "RGBA"

# fundo da paleta: o Cycles renderiza com fundo transparente (o céu ilumina, mas não aparece) e o fundo entra depois, pixel a
# pixel (alfa sobre a cor da paleta, em sRGB). Assim não depende do compositor, que mudou no Blender 5.
import os
import tempfile

import numpy as np

tmp = os.path.join(tempfile.mkdtemp(), "render.png")
cena.render.filepath = tmp
bpy.ops.render.render(write_still=True)
img = bpy.data.images.load(tmp)
w, hgt = img.size
px = np.array(img.pixels[:], dtype=np.float32).reshape(hgt, w, 4)   # PNG lido como sRGB 0–1
h = fundo.lstrip("#")
cor = np.array([int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)], dtype=np.float32)
a = px[..., 3:4]
px[..., :3] = px[..., :3] * a + cor * (1 - a)
px[..., 3] = 1.0

# rosa do norte no canto superior direito, como na vista do navegador (regra da dona: o norte sempre indicado).
# O plano x, y do IFC é o x, y do Blender; o ângulo é o do norte projetado pela câmera. Sem norte no GLB: "N?" ([MARCADOR]).
from bpy_extras.object_utils import world_to_camera_view as w2c

escuro = sum(cor) < 1.2
c_fundo = np.array([0x23, 0x28, 0x2D]) / 255 if escuro else np.array([1.0, 1.0, 1.0])            # #23282D / #FFFFFF
c_linha = np.array([0xF4, 0xF1, 0xEA]) / 255 if escuro else np.array([0x1B, 0x1F, 0x23]) / 255  # #F4F1EA / #1B1F23
c_seta = np.array([0xD9, 0xA5, 0x8C]) / 255 if escuro else np.array([0xBB, 0x6B, 0x4A]) / 255   # #D9A58C / #BB6B4A
ang, glifo = 0.0, "N?"
if norte != "-":
    nx, ny = (float(v) for v in norte.split(","))
    p0 = w2c(cena, cam, centro)
    p1 = w2c(cena, cam, centro + Vector((nx, ny, 0)).normalized() * raio * 0.2)
    ang, glifo = math.atan2((p1.x - p0.x) * w, (p1.y - p0.y) * hgt), "N"
esc = max(w, hgt) / 640                      # a rosa do navegador tem 48 px numa vista de ~640 px
r = 22 * esc
cx, cy = w - 32 * esc, hgt - 32 * esc        # y para cima (a linha 0 é a de baixo)
x0, x1, y0, y1 = int(cx - r - 2), int(cx + r + 3), int(cy - r - 2), int(cy + r + 3)
yy, xx = np.mgrid[y0:y1, x0:x1].astype(np.float32)
sx, sy = (xx - cx) / esc, (yy - cy) / esc
ca, sa = math.cos(ang), math.sin(ang)
u, v = sx * ca - sy * sa, sx * sa + sy * ca  # coordenadas da rosa (seta para +v)
d = np.hypot(sx, sy)
bloco = px[y0:y1, x0:x1, :3]
bloco[d <= 22] = c_fundo
bloco[(d > 20.8) & (d <= 22.6)] = c_linha

def dentro(poly, u, v):
    c = np.zeros(u.shape, bool)
    for (ax, ay), (bx, by) in zip(poly, poly[1:] + poly[:1]):
        cruza = ((ay > v) != (by > v)) & (u < (bx - ax) * (v - ay) / (by - ay + 1e-9) + ax)
        c ^= cruza
    return c

bloco[dentro([(0, 9), (6, -13), (0, -9), (-6, -13)], u, v)] = c_seta
# letra em 5×7 (N ou N?), acima da seta, girando junto
FONTE = {"N": ["10001", "11001", "10101", "10011", "10001", "10001", "10001"],
         "?": ["01110", "10001", "00010", "00100", "00100", "00000", "00100"]}
larg_l = 6 * len(glifo) - 1
for k, ch in enumerate(glifo):
    for lin, linha in enumerate(FONTE[ch]):
        for col, bit in enumerate(linha):
            if bit == "1":
                cu = (k * 6 + col - larg_l / 2) * 1.5
                cv = 18.5 - lin * 1.5
                bloco[(u >= cu) & (u < cu + 1.5) & (v <= cv) & (v > cv - 1.5) & (d <= 21)] = c_linha
px[y0:y1, x0:x1, :3] = bloco
saida = bpy.data.images.new("saida", w, hgt, alpha=True)
saida.pixels = px.ravel().tolist()
saida.filepath_raw = png
saida.file_format = "PNG"
saida.save()
print("imagem:", png, w, "x", hgt)
