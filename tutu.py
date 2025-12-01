import pygame
import numpy as np
from pygame.locals import *
from OpenGL.GL import *
from OpenGL.GLU import *
import random
import math
import time
import sys
import cv2
import json
import os

WIDTH, HEIGHT = 1200, 800
RANKING_FILE = "ranking.json"
GRASS_FILE = "grass.png"
GARDEN_FILE = "garden.png"

os.chdir(os.path.dirname(os.path.abspath(__file__)))

pygame.init()
pygame.font.init()

screen = pygame.display.set_mode((WIDTH, HEIGHT), DOUBLEBUF | OPENGL)
pygame.display.set_caption("Coleta de Estrelas - Trabalho CG (Compatível)")

glEnable(GL_DEPTH_TEST)
glEnable(GL_LIGHTING)
glEnable(GL_LIGHT0)
glEnable(GL_COLOR_MATERIAL)
glColorMaterial(GL_FRONT, GL_AMBIENT_AND_DIFFUSE)
glEnable(GL_NORMALIZE)
glShadeModel(GL_SMOOTH)
glEnable(GL_BLEND)
glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

glMatrixMode(GL_PROJECTION)
gluPerspective(45, WIDTH / HEIGHT, 0.1, 200.0)
glMatrixMode(GL_MODELVIEW)

class GameState:
    MENU = 0
    PLAYING = 1
    GAME_OVER = 2
    PAUSED = 3

class Objective:
    TEMPO = "TEMPO"
    ENCHER = "ENCHER"
    ZERAR = "ZERAR"

class Mode:
    SOLO = "SOLO"
    COOP = "COOP"
    DISPUTA = "DISPUTA"

class Difficulty:
    EASY = "EASY"
    NORMAL = "NORMAL"
    HARD = "HARD"

current_state = GameState.MENU
current_mode = Mode.SOLO
current_objective = Objective.TEMPO
current_difficulty = Difficulty.NORMAL

# parametros
grid_cols = 5
grid_rows = 8  # ensure at least 8
spawn_interval = 0.6
item_base_speed = 3.2
collector_width = 3.0
capacity_target_default = 10
max_items_on_screen = 12
time_limit_seconds = 60

start_time = 0
score_total = 0
ranking = {}
items = []
collectors = []
split_screen = False

font_small = pygame.font.SysFont("Arial", 16)
font_med = pygame.font.SysFont("Arial", 22)
font_big = pygame.font.SysFont("Arial", 36)

clock = pygame.time.Clock()

tex_grass = None
tex_garden = None

def load_texture_cv(path):
    if not os.path.exists(path):
        return None
    img = cv2.imread(path, cv2.IMREAD_UNCHANGED)
    if img is None:
        return None
    if img.shape[2] == 4:
        img = cv2.cvtColor(img, cv2.COLOR_BGRA2RGBA)
        mode = GL_RGBA
    else:
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        mode = GL_RGB
    img = cv2.flip(img, 0)
    h, w = img.shape[:2]
    tid = glGenTextures(1)
    glBindTexture(GL_TEXTURE_2D, tid)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_REPEAT)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_REPEAT)
    glTexImage2D(GL_TEXTURE_2D, 0, mode, w, h, 0, mode, GL_UNSIGNED_BYTE, img)
    glBindTexture(GL_TEXTURE_2D, 0)
    return tid

def init_textures():
    global tex_grass, tex_garden
    tex_grass = load_texture_cv(GRASS_FILE)
    tex_garden = load_texture_cv(GARDEN_FILE)

def load_ranking():
    global ranking
    if os.path.exists(RANKING_FILE):
        try:
            with open(RANKING_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    ranking = data
                else:
                    ranking = {}
        except:
            ranking = {}
    else:
        ranking = {}
        
        
def save_ranking():
    with open(RANKING_FILE, "w", encoding="utf-8") as f:
        json.dump(ranking, f, indent=2, ensure_ascii=False)

def add_score_to_ranking(key, entry):
    global ranking
    ranking.setdefault(key, [])
    ranking[key].append(entry)
    ranking[key] = sorted(ranking[key], key=lambda e: e.get("score", 0), reverse=True)[:3]
    save_ranking()

class Item:
    #classe estrelas
    def __init__(self, x, z, speed):
        self.x = x
        self.y = 8.0
        self.z = z
        self.speed = speed
        self.size = random.uniform(0.18, 0.28)
        self.collected = False
        self.wobble = random.random() * 2 * math.pi

    def update(self, dt):
        self.y -= self.speed * dt
        self.wobble += 3.0 * dt

    def draw(self):
        if self.collected:
            return
        glPushMatrix()
        glTranslatef(self.x, self.y, self.z)
        glMaterialfv(GL_FRONT, GL_AMBIENT, [1.0, 0.9, 0.2, 1.0])
        glMaterialfv(GL_FRONT, GL_DIFFUSE, [1.0, 0.85, 0.2, 1.0])
        glMaterialfv(GL_FRONT, GL_SPECULAR, [1.0,1.0,0.6,1.0])
        glMaterialf(GL_FRONT, GL_SHININESS, 80)
        glColor3f(1.0, 0.9, 0.2)
        glPushMatrix()
        glScalef(self.size*3.0, self.size*3.0, self.size*3.0)
        draw_tetrahedron(0.35)
        glPopMatrix()
        glPushMatrix()
        glRotatef(90,1,0,0)
        glScalef(self.size*3.0, self.size*3.0, self.size*3.0)
        draw_tetrahedron(0.35)
        glPopMatrix()
        glPopMatrix()

class Collector:
    #nave
    def __init__(self, x, z, width, player_id=1):
        self.x = x
        self.y = -3.0
        self.z = z
        self.width = width
        self.depth = 1.0
        self.score = 0
        self.load = 0
        self.lives = 3
        self.id = player_id

    def bounds(self):
        hw = self.width / 2.0
        dz = self.width * 0.45
        return (self.x - hw, self.x + hw, self.z - dz, self.z + dz)

    def draw(self):
        glPushMatrix()
        glTranslatef(self.x, self.y, self.z)
        glMaterialfv(GL_FRONT, GL_AMBIENT,  [0.4,0.4,0.4,1.0])
        glMaterialfv(GL_FRONT, GL_DIFFUSE,  [0.6,0.6,0.6,1.0])
        glMaterialfv(GL_FRONT, GL_SPECULAR, [1.0,1.0,1.0,1.0])
        glMaterialf(GL_FRONT, GL_SHININESS, 120.0)
        glColor3f(0.75,0.75,0.75)
        glPushMatrix()
        glScalef(self.width*0.5, 0.4, self.width*0.9)
        quad = gluNewQuadric()
        gluSphere(quad, 0.9, 20, 20)
        gluDeleteQuadric(quad)
        glPopMatrix()
        glPushMatrix()
        glTranslatef(0,0.5,0)
        glScalef(0.45,0.35,0.45)
        glColor3f(0.15,0.15,0.2)
        quad2 = gluNewQuadric()
        gluSphere(quad2, 0.7, 20, 20)
        gluDeleteQuadric(quad2)
        glPopMatrix()
        for o in (-0.6,0.6):
            glPushMatrix()
            glTranslatef(o, -0.1, -0.9)
            glRotatef(-90,1,0,0)
            q = gluNewQuadric()
            glColor3f(0.3,0.3,0.35)
            gluCylinder(q, 0.12, 0.08, 0.6, 12, 1)
            gluDeleteQuadric(q)
            glPopMatrix()
        glPopMatrix()

#formato estrela
def draw_tetrahedron(scale=1.0):
    pts = [(1,1,1),(-1,-1,1),(-1,1,-1),(1,-1,-1)]
    faces = [(0,1,2),(0,3,1),(0,2,3),(1,3,2)]
    glBegin(GL_TRIANGLES)
    for f in faces:
        v0 = np.array(pts[f[0]])
        v1 = np.array(pts[f[1]])
        v2 = np.array(pts[f[2]])
        n = np.cross(v1 - v0, v2 - v0)
        if np.linalg.norm(n) != 0:
            n = n / np.linalg.norm(n)
        glNormal3f(n[0], n[1], n[2])
        for idx in f:
            v = pts[idx]
            glVertex3f(v[0] * scale, v[1] * scale, v[2] * scale)
    glEnd()


def render_text(text, x, y, r=1.0, g=1.0, b=1.0, size=24, bold=False):
    font = pygame.font.SysFont("Arial", size, bold=bold)
    surf = font.render(text, True, (int(r*255), int(g*255), int(b*255)))
    data = pygame.image.tostring(surf, "RGBA", True)
    glWindowPos2f(int(x), int(y))
    glDrawPixels(surf.get_width(), surf.get_height(), GL_RGBA, GL_UNSIGNED_BYTE, data)

#cenario
def draw_sky_background():
    glDisable(GL_LIGHTING)
    glBegin(GL_QUADS)
    glColor3f(0.05, 0.05, 0.1)
    glVertex3f(-50, 30, -50)
    glVertex3f( 50, 30, -50)
    glColor3f(0.05, 0.15, 0.22)
    glVertex3f( 50, -20, -50)
    glVertex3f(-50, -20, -50)
    glEnd()
    glEnable(GL_LIGHTING)

def draw_walls_and_ground():
    glEnable(GL_TEXTURE_2D)
    if tex_garden:
        glBindTexture(GL_TEXTURE_2D, tex_garden)
    else:
        glBindTexture(GL_TEXTURE_2D, 0)
    glEnable(GL_COLOR_MATERIAL)
    glColor3f(1.0,1.0,1.0)

    glBegin(GL_QUADS)
    glNormal3f(0,0,1)
    glTexCoord2f(0,0); glVertex3f(-12.0, -4.0, -10.0)
    glTexCoord2f(4,0); glVertex3f(12.0, -4.0, -10.0)
    glTexCoord2f(4,3); glVertex3f(12.0, 6.0, -10.0)
    glTexCoord2f(0,3); glVertex3f(-12.0, 6.0, -10.0)
    glEnd()
    glBegin(GL_QUADS)
    glNormal3f(1,0,0)
    glTexCoord2f(0,0); glVertex3f(-12.0, -4.0, -10.0)
    glTexCoord2f(4,0); glVertex3f(-12.0, -4.0, 10.0)
    glTexCoord2f(4,3); glVertex3f(-12.0, 6.0, 10.0)
    glTexCoord2f(0,3); glVertex3f(-12.0, 6.0, -10.0)
    glEnd()
    glBegin(GL_QUADS)
    glNormal3f(-1,0,0)
    glTexCoord2f(0,0); glVertex3f(12.0, -4.0, 10.0)
    glTexCoord2f(4,0); glVertex3f(12.0, -4.0, -10.0)
    glTexCoord2f(4,3); glVertex3f(12.0, 6.0, -10.0)
    glTexCoord2f(0,3); glVertex3f(12.0, 6.0, 10.0)
    glEnd()

    glDisable(GL_TEXTURE_2D)
    glDisable(GL_COLOR_MATERIAL)

    glPushMatrix()
    glTranslatef(0, -3.8, 0)
    glEnable(GL_TEXTURE_2D)
    if tex_grass:
        glBindTexture(GL_TEXTURE_2D, tex_grass)
    else:
        glBindTexture(GL_TEXTURE_2D, 0)
    glBegin(GL_QUADS)
    glNormal3f(0,1,0)
    glTexCoord2f(0,0); glVertex3f(-12.0, 0.0, -12.0)
    glTexCoord2f(6,0); glVertex3f(12.0, 0.0, -12.0)
    glTexCoord2f(6,6); glVertex3f(12.0, 0.0, 12.0)
    glTexCoord2f(0,6); glVertex3f(-12.0, 0.0, 12.0)
    glEnd()
    glDisable(GL_TEXTURE_2D)
    glPopMatrix()

def draw_grid(cols, rows):
    cols = max(5, cols); rows = max(8, rows)
    width = 10.0; depth = 8.0
    xs = np.linspace(-width, width, cols)
    zs = np.linspace(-2.0, depth, rows)
    glDisable(GL_LIGHTING)
    glColor3f(0.2, 0.2, 0.3)
    glBegin(GL_LINES)
    for x in xs:
        glVertex3f(x, 0.01, -2.0); glVertex3f(x, 0.01, depth)
    for z in zs:
        glVertex3f(-width, 0.01, z); glVertex3f(width, 0.01, z)
    glEnd()
    glEnable(GL_LIGHTING)

def spawn_position_for_cols(cols):
    xs = np.linspace(-10.0, 10.0, cols)
    return xs

def spawn_item_random(cols, base_speed):
    if len(items) >= max_items_on_screen:
        return
    xs = spawn_position_for_cols(cols)
    x = random.choice(list(xs))
    z = random.uniform(-1.0, 2.0)
    speed = base_speed * (1.0 + random.uniform(-0.3, 0.6))
    items.append(Item(x, z, speed))

def reset_game_state():
    global items, start_time, score_total, collectors
    items = []
    start_time = time.time()
    score_total = 0
    collectors = [Collector(4.0, 0.0, collector_width, player_id=1),
                  Collector(-4.0, 0.0, collector_width, player_id=2)]
    for c in collectors:
        c.score = 0; c.load = 0; c.lives = 5

def check_collection_and_missed(dt):
    #colisoes
    global score_total
    for it in items[:]:
        it.update(dt)
        collected_flag = False
        for c in active_collectors():
            minx, maxx, minz, maxz = c.bounds()
            if (minx <= it.x <= maxx) and (minz <= it.z <= maxz) and (it.y <= c.y + 0.9):
                it.collected = True
                c.score += 10
                c.load += 1
                collected_flag = True
                break
        if it.y < -8 and not it.collected:
            if len(active_collectors()) == 2:
                d1 = abs(collectors[0].x - it.x)
                d2 = abs(collectors[1].x - it.x)
                loser = collectors[0] if d1 < d2 else collectors[1]
            else:
                loser = active_collectors()[0]
            loser.lives -= 1
            loser.score = max(0, loser.score - 1)
            if current_objective == Objective.ZERAR:
                loser.score = max(0, loser.score - 10)
            else:
                loser.score = max(0, loser.score - 1)
        if it.collected or it.y < -8:
            try:
                items.remove(it)
            except:
                pass

def active_collectors():
    if current_mode == Mode.SOLO:
        return [collectors[0]]
    else:
        return collectors

def draw_menu():
    glDisable(GL_DEPTH_TEST)
    glDisable(GL_LIGHTING)
    glEnable(GL_BLEND)
    glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

    #fundo escuro
    glBegin(GL_QUADS)
    glColor4f(0.00, 0.00, 0.00, 0.75)
    glVertex2f(0, 0)
    glVertex2f(WIDTH, 0)
    glColor4f(0.05, 0.05, 0.05, 0.90)
    glVertex2f(WIDTH, HEIGHT)
    glVertex2f(0, HEIGHT)
    glEnd()

    CENTER_X = WIDTH // 2

    def draw_centered(text, y, size=28, rgb=(1, 1, 1), bold=False):
        w = len(text) * (size * 0.55)
        x = CENTER_X - w // 2
        render_text(text, x, y, rgb[0], rgb[1], rgb[2], size=size, bold=bold)

    def spacing(base, offset):
        return base + offset

    y = 70

    draw_centered("COLETA DE ESTRELAS", y,
                  size=56, rgb=(1, 0.95, 0.6), bold=True)

    y = spacing(y, 110)
    draw_centered("─── Dificuldade ───", y, size=34, rgb=(0.85, 0.9, 1))
    y = spacing(y, 40)
    draw_centered("[1] EASY   [2] NORMAL   [3] HARD", y, size=26)

    y = spacing(y, 70)
    draw_centered("─── Objetivo ───", y, size=34, rgb=(0.9, 1, 0.9))
    y = spacing(y, 40)
    draw_centered("[Z] ZERAR   [E] ENCHER   [T] TEMPO", y, size=26)

    y = spacing(y, 70)
    draw_centered("─── Modo ───", y, size=34, rgb=(1, 0.9, 0.9))
    y = spacing(y, 40)
    draw_centered("[Q] SOLO   [W] COOP   [R] DISPUTA", y, size=26)

    y = spacing(y, 70)
    draw_centered("Pressione ENTER para começar", y,
                  size=30, rgb=(1, 1, 0.85))

    key = f"{current_objective}-{current_mode}"
    y = spacing(y, 80)
    draw_centered(f"TOP 3 ({key})", y,
                  size=32, rgb=(1, 0.85, 0.4), bold=True)

    arr = ranking.get(key, [])
    for i, e in enumerate(arr[:3]):
        line = f"{i+1}. {e.get('player','')}  {e.get('score',0)} pts  -  {e.get('time',0)}s"
        y = spacing(y, 35)
        draw_centered(line, y, size=24)

    glEnable(GL_DEPTH_TEST)


def draw_hud():
    render_text(f"Modo: {current_mode}   Objetivo: {current_objective}   Dificuldade: {current_difficulty}", 10, 10, 1,1,1, size=18)
    if current_objective == Objective.TEMPO and start_time:
        rem = max(0, int(time_limit_seconds - (time.time() - start_time)))
        color = (1.0,1.0,1.0) if rem > 10 else (1.0, 0.4, 0.4)
        render_text(f"Tempo restante: {rem}s", 10, 40, *color, size=18)
    if current_mode == Mode.DISPUTA:
        render_text(f"P1: {collectors[0].score} pts  Lives: {collectors[0].lives}", 10, HEIGHT - 60, 1,1,0.8, size=18)
        render_text(f"P2: {collectors[1].score} pts  Lives: {collectors[1].lives}", 10, HEIGHT - 35, 0.8,1,0.8, size=18)
    else:
        total = sum([c.score for c in active_collectors()])
        lives = sum([c.lives for c in active_collectors()])
        render_text(f"Pontos: {total}   Vidas: {lives}", 10, HEIGHT - 45, 1,1,1, size=18)
    render_text("Mov: Setas / WASD (P1)   IJKL / JKL; (P2)", WIDTH - 520, HEIGHT - 30, 0.9,0.9,0.9, size=16)

def draw_game_over():
    render_text("FIM DE JOGO", WIDTH//2 - 120, HEIGHT//2 - 40, 1,0.8,0.2, size=36, bold=True)
    if current_mode == Mode.DISPUTA:
        render_text(f"P1: {collectors[0].score}    P2: {collectors[1].score}", WIDTH//2 - 120, HEIGHT//2 + 10, 1,1,1, size=24)
    else:
        render_text(f"Score: {sum([c.score for c in active_collectors()])}", WIDTH//2 - 120, HEIGHT//2 + 10, 1,1,1, size=24)
    render_text("Pressione M para voltar ao Menu", WIDTH//2 - 150, HEIGHT//2 + 60, 0.9,0.9,0.9, size=20)

def setup_lights():
    glLightfv(GL_LIGHT0, GL_POSITION, [5.0, 12.0, 5.0, 1.0])
    glLightfv(GL_LIGHT0, GL_DIFFUSE, [0.95, 0.95, 0.9, 1.0])
    glLightfv(GL_LIGHT0, GL_SPECULAR, [1.0, 1.0, 1.0, 1.0])
    glLightfv(GL_LIGHT0, GL_AMBIENT, [0.2, 0.2, 0.2, 1.0])


camera_angle_x = 0.0
camera_angle_y = 25.0
camera_distance = 18.0
mouse_down = False
last_mouse = (0,0)
def update_camera_from_mouse(events):
    global mouse_down, last_mouse, camera_angle_x, camera_angle_y, camera_distance
    for e in events:
        if e.type == MOUSEBUTTONDOWN:
            if e.button == 1: mouse_down = True; last_mouse = pygame.mouse.get_pos()
            if e.button == 4: camera_distance = max(6.0, camera_distance - 1.0)
            if e.button == 5: camera_distance = min(60.0, camera_distance + 1.0)
        if e.type == MOUSEBUTTONUP:
            if e.button == 1: mouse_down = False
        if e.type == MOUSEMOTION and mouse_down:
            x,y = pygame.mouse.get_pos(); lx,ly = last_mouse
            dx = x - lx; dy = y - ly
            camera_angle_x += dx * 0.3
            camera_angle_y += dy * 0.2
            camera_angle_y = max(5.0, min(80.0, camera_angle_y))
            last_mouse = (x,y)

def setup_camera_transform():
    cam_x = camera_distance * math.sin(math.radians(camera_angle_x)) * math.cos(math.radians(camera_angle_y))
    cam_y = camera_distance * math.sin(math.radians(camera_angle_y))
    cam_z = camera_distance * math.cos(math.radians(camera_angle_x)) * math.cos(math.radians(camera_angle_y))
    gluLookAt(cam_x, cam_y, cam_z, 0, 0, 0, 0, 1, 0)


def apply_difficulty(diff):
    global grid_cols, grid_rows, spawn_interval, item_base_speed, collector_width, capacity_target_default, max_items_on_screen
    if diff == Difficulty.EASY:
        grid_cols = 6; grid_rows = 10
        spawn_interval = 2.0
        item_base_speed = 2.2
        collector_width = 3.6
        capacity_target_default = 6
        max_items_on_screen = 10
    elif diff == Difficulty.HARD:
        grid_cols = 4; grid_rows = 8
        spawn_interval = 0.35
        item_base_speed = 3.4
        collector_width = 2.6
        capacity_target_default = 16
        max_items_on_screen = 16
    else:
        grid_cols = 5; grid_rows = 8
        spawn_interval = 0.6
        item_base_speed = 2
        collector_width = 3.0
        capacity_target_default = 18
        max_items_on_screen = 12

    for c in collectors:
        c.width = collector_width

def start_play(mode, objective, difficulty):
    global current_mode, current_objective, current_difficulty, start_time, time_limit_seconds, split_screen
    current_mode = mode
    current_objective = objective
    current_difficulty = difficulty
    apply_difficulty(difficulty)
    reset_game_state()
    start_time = time.time()
    split_screen = (mode == Mode.DISPUTA)
    if objective == Objective.TEMPO:
        pass
    elif objective == Objective.ENCHER:
        pass
    elif objective == Objective.ZERAR:
        for c in active_collectors():
            c.score = 20

def end_game_and_save():
    key = f"{current_objective}-{current_mode}"
    if current_mode == Mode.DISPUTA:
        add_score_to_ranking(key, {"player":"P1","score":collectors[0].score,"time":int(time.time()-start_time)})
        add_score_to_ranking(key, {"player":"P2","score":collectors[1].score,"time":int(time.time()-start_time)})
    else:
        total = sum([c.score for c in active_collectors()])
        add_score_to_ranking(key, {"score": total, "time": int(time.time() - start_time)})
    # set state
    global current_state
    current_state = GameState.GAME_OVER

def update_logic(dt):

    if len(items) == 0:
        spawn_item_random(grid_cols, item_base_speed)

    check_collection_and_missed(dt)
    elapsed = time.time() - start_time if start_time else 0.0
    if current_objective == Objective.TEMPO:
        if elapsed >= time_limit_seconds:
            end_game_and_save()
    if current_objective == Objective.ENCHER:
        for c in active_collectors():
            if c.load >= capacity_target_default:
                end_game_and_save()
    if current_objective == Objective.ZERAR:
        for c in active_collectors():
            if c.lives <= 0:
                end_game_and_save()
                return

        if current_mode != Mode.DISPUTA:
            total = sum([c.score for c in active_collectors()])
            if total <= 0:
                end_game_and_save()


def main():
    global current_state, current_mode, current_objective, current_difficulty, tex_grass, tex_garden, start_time
    init_textures()
    load_ranking()
    apply_difficulty(current_difficulty)
    reset_game_state()
    setup_lights()

    running = True
    last = time.time()

    while running:
        now = time.time()
        dt = now - last
        last = now

        events = pygame.event.get()
        for e in events:
            if e.type == QUIT:
                running = False
            if e.type == KEYDOWN:
                if e.key == K_ESCAPE:
                    running = False
                if current_state == GameState.MENU:
                    if e.key == K_1:
                        current_difficulty = Difficulty.EASY; apply_difficulty(current_difficulty)
                    if e.key == K_2:
                        current_difficulty = Difficulty.NORMAL; apply_difficulty(current_difficulty)
                    if e.key == K_3:
                        current_difficulty = Difficulty.HARD; apply_difficulty(current_difficulty)
                    if e.key == K_z:
                        current_objective = Objective.ZERAR
                    if e.key == K_e:
                        current_objective = Objective.ENCHER
                    if e.key == K_t:
                        current_objective = Objective.TEMPO
                    if e.key == K_q:
                        current_mode = Mode.SOLO
                    if e.key == K_w:
                        current_mode = Mode.COOP
                    if e.key == K_r:
                        current_mode = Mode.DISPUTA
                    if e.key == K_RETURN:
                        start_play(current_mode, current_objective, current_difficulty)
                        current_state = GameState.PLAYING
                elif current_state == GameState.GAME_OVER:
                    if e.key == K_m:
                        current_state = GameState.MENU
                elif current_state == GameState.PLAYING:
                    if e.key == K_p:
                        current_state = GameState.PAUSED
                elif current_state == GameState.PAUSED:
                    if e.key == K_p:
                        current_state = GameState.PLAYING

        update_camera_from_mouse(events)

        keys = pygame.key.get_pressed()
        if current_state == GameState.PLAYING:
            speed = 6.0 * dt

            if keys[K_LEFT] or keys[K_a]:
                collectors[0].x -= collectors[0].width * 0.4 * dt * 5
            if keys[K_RIGHT] or keys[K_d]:
                collectors[0].x += collectors[0].width * 0.4 * dt * 5
            if keys[K_UP] or keys[K_w]:
                collectors[0].z -= collectors[0].width * 0.2 * dt * 5
            if keys[K_DOWN] or keys[K_s]:
                collectors[0].z += collectors[0].width * 0.2 * dt * 5

            if current_mode in (Mode.COOP, Mode.DISPUTA):
                if keys[K_j]:
                    collectors[1].x -= collectors[1].width * 0.4 * dt * 5
                if keys[K_l]:
                    collectors[1].x += collectors[1].width * 0.4 * dt * 5
                if keys[K_i]:
                    collectors[1].z -= collectors[1].width * 0.2 * dt * 5
                if keys[K_k]:
                    collectors[1].z += collectors[1].width * 0.2 * dt * 5


            for c in collectors:
                c.x = max(-10.0, min(10.0, c.x))
                c.z = max(-4.0, min(10.0, c.z))

            update_logic(dt)

        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        glLoadIdentity()

        setup_camera_transform()
        setup_lights()

        draw_sky_background()
        draw_walls_and_ground()
        draw_grid(grid_cols, grid_rows)

        for it in items:
            it.draw()

        for c in collectors:
            if current_mode == Mode.SOLO and c.id == 2:
                continue
            c.draw()


        glMatrixMode(GL_PROJECTION)
        glPushMatrix()
        glLoadIdentity()
        gluOrtho2D(0, WIDTH, HEIGHT, 0)
        glMatrixMode(GL_MODELVIEW)
        glPushMatrix()
        glLoadIdentity()
        glDisable(GL_LIGHTING)
        glDisable(GL_DEPTH_TEST)

        if current_state == GameState.MENU:
            draw_menu()
        elif current_state == GameState.PLAYING:
            draw_hud()
        elif current_state == GameState.GAME_OVER:
            draw_game_over()
        elif current_state == GameState.PAUSED:
            render_text("JOGO PAUSADO - P para continuar", WIDTH//2 - 180, HEIGHT//2, 1,1,0, size=26)

        glEnable(GL_DEPTH_TEST)
        glEnable(GL_LIGHTING)
        glMatrixMode(GL_PROJECTION)
        glPopMatrix()
        glMatrixMode(GL_MODELVIEW)
        glPopMatrix()

        pygame.display.flip()
        clock.tick(60)


        if current_state == GameState.PLAYING:
            for c in active_collectors():
                if c.lives <= 0:
                    end_game_and_save()
                    break

    pygame.quit()
    sys.exit(0)

if __name__ == "__main__":
    main()
