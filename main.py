import sys
import os
import math
import time
import random
import ctypes
import subprocess
from dataclasses import dataclass, field
from typing import List, Tuple, Optional

import pygame
from pygame.locals import *

from OpenGL.GL import *
from OpenGL.GLU import *
from OpenGL.GLUT import *
from PIL import Image

try:
    glutInit()
except:
    pass

if not hasattr(sys.modules[__name__], "GLUT_BITMAP_HELVETICA_18"):
    GLUT_BITMAP_HELVETICA_18 = ctypes.c_void_p(0x0008)
    GLUT_BITMAP_HELVETICA_12 = ctypes.c_void_p(0x0006)
    GLUT_BITMAP_TIMES_ROMAN_24 = ctypes.c_void_p(0x0005)

COLS = 12
SCREEN_W = 800
SCREEN_H = 800

STATE_MENU = 0
STATE_DIFFICULTY_SELECT = 1
STATE_PLAYING = 2
STATE_PAUSED = 3
STATE_GAMEOVER = 4
STATE_WIN = 5

GAME_MODE_SOLO = 0
GAME_MODE_MULTI = 1

DIFFICULTY_ORDER = ['Facil', 'Normal', 'Dificil', 'Dante Must Die']
DIFFICULTY_SETTINGS = {
    'Facil':  {'spawn_interval': 2.0, 'speed': 6.0, 'spawn_min': 1, 'spawn_max': 1},
    'Normal': {'spawn_interval': 1.5, 'speed': 9.0, 'spawn_min': 1, 'spawn_max': 2},
    'Dificil':{'spawn_interval': 1.0, 'speed': 14.0, 'spawn_min': 2, 'spawn_max': 3},
    'Dante Must Die': {'spawn_interval': 0.7, 'speed': 20.0, 'spawn_min': 2, 'spawn_max': 3}
}

TEXTURE_CACHE = {}

def get_asset_path(filename, folder='images'):
    base_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_dir, folder, filename)

def load_texture(filename):
    path = get_asset_path(filename)
    if path in TEXTURE_CACHE:
        return TEXTURE_CACHE[path]
    try:
        img = Image.open(path)
        img = img.transpose(Image.FLIP_TOP_BOTTOM)
        img_data = img.convert("RGBA").tobytes()
        tex_id = glGenTextures(1)
        glBindTexture(GL_TEXTURE_2D, tex_id)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_REPEAT)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_REPEAT)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, img.width, img.height, 0, GL_RGBA, GL_UNSIGNED_BYTE, img_data)
        TEXTURE_CACHE[path] = tex_id
        return tex_id
    except:
        return None

def load_sound(filename):
    path = get_asset_path(filename, folder='sounds')
    try:
        return pygame.mixer.Sound(path)
    except:
        return None

def launch_extra_game():
    try:
        game_path = os.path.join("extra", "main.py")
        if not os.path.exists(game_path):
            print("Erro: extra/main.py não encontrado.")
            return
        subprocess.run([sys.executable, "main.py"], cwd="extra")
        pygame.display.set_mode((SCREEN_W, SCREEN_H), DOUBLEBUF | OPENGL)
        glEnable(GL_DEPTH_TEST)
        glEnable(GL_TEXTURE_2D)
    except Exception as e:
        print(f"Erro ao iniciar Extras: {e}")

@dataclass
class PlayerState:
    x: float = COLS / 2
    z: float = 1.0
    active: bool = True
    lives: int = 5
    score: int = 0
    dead: bool = False
    speed_level: int = 1 

    def get_speed_factor(self):
        return 1.0 + (self.speed_level - 1) * 0.25

@dataclass
class GameState:
    p1: PlayerState = field(default_factory=PlayerState)
    p2: PlayerState = field(default_factory=PlayerState)
    camera_x: float = COLS / 2
    camera_y: float = 3.0
    camera_z: float = 12.0
    
    cam_pitch: float = 0.0
    cam_yaw: float = 0.0
    
    stars: List[list] = field(default_factory=list)
    explosions: List[list] = field(default_factory=list)
    falling_stars: List[list] = field(default_factory=list) 
    
    state_id: int = STATE_MENU
    game_mode: int = GAME_MODE_SOLO
    
    menu_selection: int = 0
    difficulty_selection: int = 1
    
    end_screen_selection: int = 0 
    pause_selection: int = 0
    
    time_elapsed: float = 0.0
    max_time: float = 60.0 
    current_difficulty: str = 'Normal'
    spawn_timer: float = 0.0
    
    earth_texture: Optional[int] = None
    life_texture: Optional[int] = None
    galaxy_texture: Optional[int] = None
    alien_texture: Optional[int] = None
    sun_texture: Optional[int] = None
    
    menu_anim: float = 0.0
    moon_angle: float = 0.0
    
    snd_coin: Optional[pygame.mixer.Sound] = None
    snd_gameover: Optional[pygame.mixer.Sound] = None
    snd_item: Optional[pygame.mixer.Sound] = None
    snd_life: Optional[pygame.mixer.Sound] = None
    snd_win_music: Optional[pygame.mixer.Sound] = None

    def reset(self):
        start_lives = 1 if self.current_difficulty == 'Dante Must Die' else 5
        
        start_x_p1 = COLS/4 if self.game_mode == GAME_MODE_MULTI else COLS/2
        self.p1 = PlayerState(x=start_x_p1, active=True, lives=start_lives, dead=False, score=0, speed_level=1)
        
        start_x_p2 = (COLS/4) * 3
        self.p2 = PlayerState(x=start_x_p2, active=(self.game_mode == GAME_MODE_MULTI), lives=start_lives if self.game_mode == GAME_MODE_MULTI else 0, dead=False, score=0, speed_level=1)
        
        self.stars.clear()
        self.explosions.clear()
        self.time_elapsed = 0.0
        self.end_screen_selection = 0 
        self.pause_selection = 0
        self.spawn_timer = 0.0
        self.cam_pitch = 0.0
        self.cam_yaw = 0.0

CUBE_FACES = [
    ((0, 0, 1), ((-0.5, -0.5, 0.5), (0.5, -0.5, 0.5), (0.5, 0.5, 0.5), (-0.5, 0.5, 0.5))),
    ((0, 0, -1), ((-0.5, -0.5, -0.5), (-0.5, 0.5, -0.5), (0.5, 0.5, -0.5), (0.5, -0.5, -0.5))),
    ((-1, 0, 0), ((-0.5, -0.5, -0.5), (-0.5, -0.5, 0.5), (-0.5, 0.5, 0.5), (-0.5, 0.5, -0.5))),
    ((1, 0, 0), ((0.5, -0.5, -0.5), (0.5, 0.5, -0.5), (0.5, 0.5, 0.5), (0.5, -0.5, 0.5))),
    ((0, 1, 0), ((-0.5, 0.5, -0.5), (-0.5, 0.5, 0.5), (0.5, 0.5, 0.5), (0.5, 0.5, -0.5))),
    ((0, -1, 0), ((-0.5, -0.5, -0.5), (0.5, -0.5, -0.5), (0.5, -0.5, 0.5), (-0.5, -0.5, 0.5))),
]

class Renderer:
    def __init__(self, state: GameState):
        self.state = state
        self.lists = {}

    def init_gl(self):
        glEnable(GL_DEPTH_TEST)
        glEnable(GL_TEXTURE_2D)
        glEnable(GL_LIGHTING)
        glEnable(GL_LIGHT0)
        glClearColor(0.0, 0.0, 0.0, 1.0) 
        glEnable(GL_COLOR_MATERIAL)
        glColorMaterial(GL_FRONT_AND_BACK, GL_AMBIENT_AND_DIFFUSE)
        
        self.state.earth_texture = load_texture("earth.jpg")
        self.state.life_texture = load_texture("life_icon.png")
        self.state.galaxy_texture = load_texture("galaxy.jpg")
        self.state.alien_texture = load_texture("alien.jpg")
        self.state.sun_texture = load_texture("sun.jpg")
        
        self.state.snd_coin = load_sound("coin.WAV")
        self.state.snd_gameover = load_sound("gameover.wav")
        self.state.snd_item = load_sound("item.WAV")
        self.state.snd_life = load_sound("life.WAV")
        self.state.snd_win_music = load_sound("musicaVitoria.wav")
        
        self._gen_falling_stars()
        self._compile_lists()
        self.resize(SCREEN_W, SCREEN_H)

    def resize(self, w, h):
        if h == 0: h = 1
        glViewport(0, 0, w, h)
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        gluPerspective(60, w / h, 0.1, 200.0) 
        glMatrixMode(GL_MODELVIEW)

    def _gen_falling_stars(self):
        self.state.falling_stars = []
        for _ in range(200):
            self.state.falling_stars.append([random.uniform(-25, 35), random.uniform(-15, 25), random.uniform(-20, 5), random.uniform(0.02, 0.15)])

    def _emit_cube(self):
        glBegin(GL_QUADS)
        for n, f in CUBE_FACES:
            glNormal3f(*n)
            for v in f: glVertex3f(*v)
        glEnd()
    
    def _emit_textured_quad(self):
        glNormal3f(0, 0, 1)
        glBegin(GL_QUADS)
        glTexCoord2f(0, 0); glVertex3f(-0.5, -0.5, 0)
        glTexCoord2f(1, 0); glVertex3f( 0.5, -0.5, 0)
        glTexCoord2f(1, 1); glVertex3f( 0.5,  0.5, 0)
        glTexCoord2f(0, 1); glVertex3f(-0.5,  0.5, 0)
        glEnd()

    def _draw_text_centered(self, text, y_pos, font=GLUT_BITMAP_HELVETICA_18):
        char_width = 9 
        if font == GLUT_BITMAP_TIMES_ROMAN_24: char_width = 14
        width = len(text) * char_width
        x = (SCREEN_W - width) / 2
        glRasterPos2f(x, y_pos)
        for c in text: glutBitmapCharacter(font, ord(c))

    def _compile_lists(self):
        sid = glGenLists(1)
        glNewList(sid, GL_COMPILE)
        glPushMatrix()
        glScalef(0.4, 0.2, 1.5)
        self._emit_cube()
        glPopMatrix()
        glPushMatrix()
        glTranslatef(0.3, 0, -0.5)
        glScalef(0.1, 0.1, 0.8)
        self._emit_cube()
        glPopMatrix()
        glPushMatrix()
        glTranslatef(-0.3, 0, -0.5)
        glScalef(0.1, 0.1, 0.8)
        self._emit_cube()
        glPopMatrix()
        glEndList()
        self.lists['ship'] = sid

        eid = glGenLists(1)
        glNewList(eid, GL_COMPILE)
        glColor3f(0.2, 1.0, 0.2)
        glPushMatrix()
        glScalef(0.4, 0.35, 0.35)
        gluSphere(gluNewQuadric(), 1.0, 16, 16)
        glPopMatrix()
        glColor3f(0.0, 0.0, 0.0)
        glPushMatrix(); glTranslatef(-0.15, 0.05, 0.25); glRotatef(-20, 0, 1, 0); glScalef(0.12, 0.08, 0.05); gluSphere(gluNewQuadric(), 1.0, 10, 10); glPopMatrix()
        glPushMatrix(); glTranslatef(0.15, 0.05, 0.25); glRotatef(20, 0, 1, 0); glScalef(0.12, 0.08, 0.05); gluSphere(gluNewQuadric(), 1.0, 10, 10); glPopMatrix()
        glColor3f(0.2, 0.8, 0.2)
        glPushMatrix(); glTranslatef(0, -0.5, 0); glRotatef(-90, 1, 0, 0); gluCylinder(gluNewQuadric(), 0.1, 0.2, 0.5, 10, 1); glPopMatrix()
        glEndList()
        self.lists['et_3d'] = eid

        cid = glGenLists(1)
        glNewList(cid, GL_COMPILE)
        glColor3f(1.0, 0.84, 0.0)
        glPushMatrix()
        gluCylinder(gluNewQuadric(), 0.35, 0.35, 0.1, 20, 1)
        glPopMatrix()
        gluDisk(gluNewQuadric(), 0, 0.35, 20, 1)
        glPushMatrix()
        glTranslatef(0, 0, 0.1)
        gluDisk(gluNewQuadric(), 0, 0.35, 20, 1)
        glPopMatrix()
        glEndList()
        self.lists['coin_3d'] = cid

    def draw(self):
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        glLoadIdentity()
        st = self.state
        
        if st.state_id not in [STATE_MENU, STATE_DIFFICULTY_SELECT]:
            self._draw_galaxy_bg()

        if st.state_id in [STATE_MENU, STATE_DIFFICULTY_SELECT]:
            gluLookAt(0, 0, 25, 0, 0, 0, 0, 1, 0)
            self._draw_falling_stars()
            self._draw_menu_ui()
        else:
            center_x = COLS / 2
            
            cam_rad_yaw = math.radians(st.cam_yaw)
            cam_rad_pitch = math.radians(st.cam_pitch)
            
            look_x = math.sin(cam_rad_yaw) * math.cos(cam_rad_pitch)
            look_y = math.sin(cam_rad_pitch)
            look_z = -math.cos(cam_rad_yaw) * math.cos(cam_rad_pitch)
            
            cam_pos_x = center_x
            cam_pos_y = st.camera_y
            cam_pos_z = st.camera_z
            
            gluLookAt(cam_pos_x, cam_pos_y, cam_pos_z, 
                      cam_pos_x + look_x, cam_pos_y + look_y, cam_pos_z + look_z, 
                      0, 1, 0)
            
            glLightfv(GL_LIGHT0, GL_POSITION, [center_x, 20.0, 5.0, 1.0])
            
            self._draw_falling_stars()
            self._draw_sun()
            self._draw_earth_ingame(center_x)
            
            if st.game_mode == GAME_MODE_MULTI:
                self._draw_separator()

            if st.p1.active and not st.p1.dead:
                self._draw_ship(st.p1, (0.4, 0.6, 1.0))
            if st.p2.active and not st.p2.dead:
                self._draw_ship(st.p2, (1.0, 0.6, 0.4))
                
            for s in st.stars:
                glPushMatrix()
                glTranslatef(s[0], s[1], s[2])
                glRotatef(s[9], 0.0, 0.0, 1.0)
                glRotatef(s[9]*0.5, 0.0, 1.0, 0.0)
                sz = s[4]
                glScalef(sz, sz, sz)
                if s[3] == 'enemy':
                    if self.lists.get('et_3d'): glCallList(self.lists['et_3d'])
                    else: self._emit_cube()
                elif s[3] == 'pickup':
                    if self.lists.get('coin_3d'): glCallList(self.lists['coin_3d'])
                    else: self._emit_cube()
                glPopMatrix()
            
            self._draw_explosions()
            self._draw_hud()
            
            if st.state_id == STATE_PAUSED:
                self._draw_overlay("PAUSADO", ["CONTINUAR", "REINICIAR", "MENU PRINCIPAL"], st.pause_selection)
            elif st.state_id == STATE_GAMEOVER:
                self._draw_end_screen("GAME OVER", (1, 0.2, 0.2), "TENTAR NOVAMENTE", "MENU PRINCIPAL")
            elif st.state_id == STATE_WIN:
                win_text = "VITORIA!"
                if st.game_mode == GAME_MODE_MULTI:
                    if st.p1.score > st.p2.score: win_text = "JOGADOR 1 VENCEU!"
                    elif st.p2.score > st.p1.score: win_text = "JOGADOR 2 VENCEU!"
                    else: win_text = "EMPATE!"
                self._draw_end_screen(win_text, (0.2, 1.0, 0.2), "JOGAR NOVAMENTE", "MENU PRINCIPAL")

    def _draw_separator(self):
        glDisable(GL_LIGHTING)
        glDisable(GL_TEXTURE_2D)
        glColor3f(1, 1, 1)
        glLineWidth(2.0)
        glBegin(GL_LINES)
        glVertex3f(COLS/2, 0, 5)
        glVertex3f(COLS/2, 0, -100)
        glEnd()
        glEnable(GL_LIGHTING)

    def _draw_galaxy_bg(self):
        glMatrixMode(GL_PROJECTION); glPushMatrix(); glLoadIdentity(); glOrtho(0, 1, 0, 1, -1, 1)
        glMatrixMode(GL_MODELVIEW); glPushMatrix(); glLoadIdentity()
        glDisable(GL_DEPTH_TEST); glDisable(GL_LIGHTING); glEnable(GL_TEXTURE_2D)
        if self.state.galaxy_texture: glBindTexture(GL_TEXTURE_2D, self.state.galaxy_texture); glColor3f(1, 1, 1)
        else: glColor3f(0.1, 0.1, 0.2)
        glBegin(GL_QUADS); glTexCoord2f(0,0); glVertex2f(0, 0); glTexCoord2f(1,0); glVertex2f(1, 0); glTexCoord2f(1,1); glVertex2f(1, 1); glTexCoord2f(0,1); glVertex2f(0, 1); glEnd()
        glEnable(GL_LIGHTING); glEnable(GL_DEPTH_TEST)
        glPopMatrix(); glMatrixMode(GL_PROJECTION); glPopMatrix(); glMatrixMode(GL_MODELVIEW)

    def _draw_falling_stars(self):
        glDisable(GL_LIGHTING); glDisable(GL_TEXTURE_2D); glPointSize(2); glBegin(GL_POINTS); glColor3f(1, 1, 1)
        for s in self.state.falling_stars: glVertex3f(s[0], s[1], s[2])
        glEnd(); glEnable(GL_LIGHTING)

    def _draw_sun(self):
        glEnable(GL_TEXTURE_2D)
        if self.state.sun_texture:
            glBindTexture(GL_TEXTURE_2D, self.state.sun_texture)
        else:
            glDisable(GL_TEXTURE_2D)
        glPushMatrix()
        glTranslatef(COLS/2, 50, -20) 
        glRotatef(self.state.moon_angle * 0.5, 0, 1, 0)
        glColor3f(1, 1, 1)
        glDisable(GL_LIGHTING) 
        quad = gluNewQuadric()
        gluQuadricTexture(quad, GL_TRUE)
        gluSphere(quad, 20, 40, 40)
        glEnable(GL_LIGHTING)
        glPopMatrix()
        glDisable(GL_TEXTURE_2D)

    def _draw_ship(self, p, color):
        glDisable(GL_TEXTURE_2D); glPushMatrix(); glTranslatef(p.x, 0.2, p.z); glColor3f(*color)
        if self.lists.get('ship'): glCallList(self.lists['ship'])
        glPopMatrix()

    def _draw_earth_ingame(self, cam_x):
        glEnable(GL_TEXTURE_2D)
        if self.state.earth_texture: glBindTexture(GL_TEXTURE_2D, self.state.earth_texture)
        else: glDisable(GL_TEXTURE_2D)
        glPushMatrix(); glTranslatef(cam_x, -95, 20); glRotatef(self.state.moon_angle, 0, 1, 0)
        glColor3f(1,1,1); q = gluNewQuadric(); gluQuadricTexture(q, GL_TRUE); gluSphere(q, 90, 50, 50)
        glPopMatrix(); glDisable(GL_TEXTURE_2D)

    def _draw_explosions(self):
        glDisable(GL_LIGHTING); glDisable(GL_TEXTURE_2D); glEnable(GL_BLEND); glBlendFunc(GL_SRC_ALPHA, GL_ONE)
        for e in self.state.explosions:
            alpha = 1.0 - (e[4]/e[5]); glColor4f(1, 0.8, 0.3, alpha)
            glPushMatrix(); glTranslatef(e[0],e[1],e[2]); glScalef(e[3]+e[4]*2, e[3]+e[4]*2, e[3]+e[4]*2); self._emit_cube(); glPopMatrix()
        glDisable(GL_BLEND); glEnable(GL_LIGHTING)

    def _draw_menu_ui(self):
        self._setup_2d()
        
        # Título Dinâmico
        if self.state.state_id == STATE_MENU:
            title = "DEFENSORES DA TERRA"
            opts = ["Jogador Solo", "Dois Jogadores", "Extras", "Sair"]
            sel = self.state.menu_selection
        else:
            title = "SELECIONAR DIFICULDADE"
            opts = ["Facil", "Normal", "Dificil", "Dante Must Die"]
            sel = self.state.difficulty_selection

        glColor3f(0.3, 0.7, 1.0)
        self._draw_text_centered(title, 150, GLUT_BITMAP_TIMES_ROMAN_24)
        
        # Centralização Vertical
        total_h = len(opts) * 40
        start_y = (SCREEN_H - total_h) / 2 + 50
        
        for i, opt in enumerate(opts):
            if i == sel: glColor3f(0.8, 0.2, 1.0) 
            else: glColor3f(0.7, 0.7, 0.7)
            
            # Centralização Horizontal
            self._draw_text_centered(opt, start_y + i * 40)
            
        self._teardown_2d()

    def _draw_end_screen(self, title_text, title_color, opt1, opt2):
        self._setup_2d()
        glEnable(GL_BLEND); glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA); glColor4f(0,0,0,0.85)
        glBegin(GL_QUADS); glVertex2f(0,0); glVertex2f(SCREEN_W,0); glVertex2f(SCREEN_W, SCREEN_H); glVertex2f(0, SCREEN_H); glEnd(); glDisable(GL_BLEND)
        glColor3f(*title_color)
        self._draw_text_centered(title_text, SCREEN_H/2 - 80, GLUT_BITMAP_TIMES_ROMAN_24)
        st = self.state
        score_txt = f"P1: {st.p1.score}" + (f"  P2: {st.p2.score}" if st.game_mode == GAME_MODE_MULTI else "")
        glColor3f(1, 1, 1)
        self._draw_text_centered(score_txt, SCREEN_H/2 - 40)
        sel = st.end_screen_selection
        if sel == 0: glColor3f(0.8, 0.2, 1.0)
        else: glColor3f(0.5, 0.5, 0.5)
        self._draw_text_centered(opt1, SCREEN_H/2 + 30)
        if sel == 1: glColor3f(0.8, 0.2, 1.0)
        else: glColor3f(0.5, 0.5, 0.5)
        self._draw_text_centered(opt2, SCREEN_H/2 + 70)
        self._teardown_2d()

    def _draw_overlay(self, title, options, selection):
        self._setup_2d()
        glEnable(GL_BLEND); glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA); glColor4f(0,0,0,0.7)
        glBegin(GL_QUADS); glVertex2f(0,0); glVertex2f(SCREEN_W,0); glVertex2f(SCREEN_W, SCREEN_H); glVertex2f(0, SCREEN_H); glEnd()
        glColor3f(1,1,1)
        self._draw_text_centered(title, SCREEN_H/2 - 60, GLUT_BITMAP_TIMES_ROMAN_24)
        
        total_h = len(options) * 40
        start_y = (SCREEN_H - total_h) / 2 + 30
        
        for i, opt in enumerate(options):
            if i == selection: glColor3f(0.8, 0.2, 1.0)
            else: glColor3f(0.5, 0.5, 0.5)
            self._draw_text_centered(opt, start_y + i*40)
        self._teardown_2d()

    def _draw_hud(self):
        self._setup_2d(); st = self.state
        if st.p1.active and not st.p1.dead: self._draw_player_hud(20, st.p1, (0.4, 0.6, 1.0), "P1")
        if st.p2.active and not st.p2.dead: self._draw_player_hud(SCREEN_W - 160, st.p2, (1.0, 0.6, 0.4), "P2")
        glColor3f(1,1,1); time_left = max(0, int(st.max_time - st.time_elapsed))
        txt = f"Tempo: {time_left}s"
        self._draw_text_centered(txt, 40)
        self._teardown_2d()

    def _draw_player_hud(self, x, p, color, label):
        if self.state.life_texture:
            glEnable(GL_TEXTURE_2D); glBindTexture(GL_TEXTURE_2D, self.state.life_texture); glColor3f(1,1,1)
            for i in range(p.lives):
                xp = x + i * 25
                glBegin(GL_QUADS); glTexCoord2f(0,0); glVertex2f(xp, 20); glTexCoord2f(1,0); glVertex2f(xp+20, 20); glTexCoord2f(1,1); glVertex2f(xp+20, 40); glTexCoord2f(0,1); glVertex2f(xp, 40); glEnd()
            glDisable(GL_TEXTURE_2D)
        else:
            glColor3f(*color); glRasterPos2f(x, 40); s = f"Lives: {p.lives}"
            for c in s: glutBitmapCharacter(GLUT_BITMAP_HELVETICA_18, ord(c))
        glColor3f(1,1,1); glRasterPos2f(x, 60)
        for c in f"{label} Score: {p.score}": glutBitmapCharacter(GLUT_BITMAP_HELVETICA_12, ord(c))
        glColor3f(0.5, 0.8, 1.0); glRasterPos2f(x, 80)
        for c in f"Speed: {p.speed_level}": glutBitmapCharacter(GLUT_BITMAP_HELVETICA_12, ord(c))

    def _setup_2d(self):
        glMatrixMode(GL_PROJECTION); glPushMatrix(); glLoadIdentity(); glOrtho(0, SCREEN_W, SCREEN_H, 0, -1, 1)
        glMatrixMode(GL_MODELVIEW); glPushMatrix(); glLoadIdentity(); glDisable(GL_LIGHTING); glDisable(GL_DEPTH_TEST)

    def _teardown_2d(self):
        glEnable(GL_DEPTH_TEST); glEnable(GL_LIGHTING); glMatrixMode(GL_PROJECTION); glPopMatrix(); glMatrixMode(GL_MODELVIEW); glPopMatrix()

def spawn_entities(state, dt):
    diff = DIFFICULTY_SETTINGS[state.current_difficulty]
    state.spawn_timer += dt
    if state.spawn_timer >= diff['spawn_interval']:
        state.spawn_timer = 0
        count = random.randint(diff['spawn_min'], diff['spawn_max'])
        
        def spawn_in_range(min_x, max_x):
            lane = random.uniform(min_x, max_x)
            state.stars.append([lane, 0, random.uniform(-100, -60), 'pickup' if random.random() < 0.1 else 'enemy', 0.6, 0,0,0, 1, 0])

        for _ in range(count):
            if state.game_mode == GAME_MODE_SOLO:
                spawn_in_range(0, COLS)
            else:
                if random.random() < 0.5: spawn_in_range(0, COLS/2)
                else: spawn_in_range(COLS/2, COLS)
                if count > 1:
                     spawn_in_range(0, COLS/2)
                     spawn_in_range(COLS/2, COLS)

def handle_input(state, dt_raw):
    keys = pygame.key.get_pressed()
    
    speed_p1 = 10.0 * dt_raw * state.p1.get_speed_factor()
    max_x_p1 = (COLS/2) - 0.7 if state.game_mode == GAME_MODE_MULTI else COLS
    if state.p1.active and not state.p1.dead:
        if keys[K_a]: state.p1.x = max(0.0, state.p1.x - speed_p1)
        if keys[K_d]: state.p1.x = min(max_x_p1, state.p1.x + speed_p1)
    
    speed_p2 = 10.0 * dt_raw * state.p2.get_speed_factor()
    min_x_p2 = (COLS/2) + 0.7
    if state.game_mode == GAME_MODE_MULTI and state.p2.active and not state.p2.dead:
        if keys[K_LEFT]: state.p2.x = max(min_x_p2, state.p2.x - speed_p2)
        if keys[K_RIGHT]: state.p2.x = min(COLS, state.p2.x + speed_p2)

def update_game(state, real_dt):
    for s in state.falling_stars:
        s[1] -= s[3]
        if s[1] < -10: s[1], s[0] = 20, random.uniform(-20, 30)

    if state.state_id != STATE_PLAYING: return

    handle_input(state, real_dt)
    
    state.time_elapsed += real_dt
    if state.time_elapsed >= state.max_time:
        state.state_id = STATE_WIN
        if state.snd_win_music: state.snd_win_music.play()
        return

    diff = DIFFICULTY_SETTINGS[state.current_difficulty]
    state.moon_angle += real_dt * 5
    spawn_entities(state, real_dt)

    active_players = []
    if state.p1.active and not state.p1.dead: active_players.append(state.p1)
    if state.p2.active and not state.p2.dead: active_players.append(state.p2)

    if not active_players:
        state.state_id = STATE_GAMEOVER
        if state.snd_gameover: state.snd_gameover.play()
        return

    toremove = []
    for s in state.stars:
        current_speed_factor = 1.0
        if state.game_mode == GAME_MODE_MULTI:
            if s[0] < COLS/2: current_speed_factor = state.p1.get_speed_factor()
            else: current_speed_factor = state.p2.get_speed_factor()
        else:
            current_speed_factor = state.p1.get_speed_factor()

        dt_local = real_dt * current_speed_factor
        
        s[2] += diff['speed'] * dt_local
        s[9] += 90 * dt_local
        
        hit = False
        target_players = active_players
        if state.game_mode == GAME_MODE_MULTI:
            if s[0] < COLS/2: target_players = [state.p1] if state.p1.active and not state.p1.dead else []
            else: target_players = [state.p2] if state.p2.active and not state.p2.dead else []

        for p in target_players:
            if abs(s[0] - p.x) < 1.2 and abs(s[2] - p.z) < 1.0:
                if s[3] == 'enemy':
                    p.score += 1
                    if state.snd_item: state.snd_item.play()
                    toremove.append(s); hit = True
                elif s[3] == 'pickup':
                    p.score += 2
                    if state.snd_coin: state.snd_coin.play()
                    toremove.append(s); hit = True
                if hit: break
        if hit: continue
        
        if s[2] > 5.0:
            if s[3] == 'enemy':
                victim = None
                if state.game_mode == GAME_MODE_MULTI:
                    if s[0] < COLS/2 and state.p1.active and not state.p1.dead: victim = state.p1
                    elif s[0] >= COLS/2 and state.p2.active and not state.p2.dead: victim = state.p2
                else:
                    if state.p1.active and not state.p1.dead: victim = state.p1
                
                if victim:
                    victim.lives -= 1
                    if victim.lives <= 0: victim.dead = True
                    if state.snd_life: state.snd_life.play()
            toremove.append(s)

    for r in toremove:
        if r in state.stars: state.stars.remove(r)
    for e in state.explosions: e[4] += real_dt
    state.explosions = [e for e in state.explosions if e[4] < e[5]]

def main():
    pygame.init(); pygame.mixer.init()
    pygame.display.set_mode((SCREEN_W, SCREEN_H), DOUBLEBUF | OPENGL)
    pygame.display.set_caption("Defensores da Terra")
    state = GameState(); renderer = Renderer(state); renderer.init_gl()
    clock = pygame.time.Clock(); running = True
    
    mouse_drag = False

    while running:
        real_dt = clock.tick(60) / 1000.0
        for event in pygame.event.get():
            if event.type == QUIT: running = False
            if event.type == VIDEORESIZE: renderer.resize(event.w, event.h)
            
            if event.type == MOUSEBUTTONDOWN and event.button == 1:
                pygame.mouse.get_rel()
                mouse_drag = True
            elif event.type == MOUSEBUTTONUP and event.button == 1:
                mouse_drag = False
            elif event.type == MOUSEMOTION and mouse_drag:
                dx, dy = event.rel
                state.cam_yaw += dx * 0.3
                state.cam_pitch -= dy * 0.3
                state.cam_pitch = max(-89, min(89, state.cam_pitch))

            if event.type == KEYDOWN:
                if state.state_id == STATE_PLAYING:
                    if event.key == K_w: state.p1.speed_level = min(5, state.p1.speed_level + 1)
                    elif event.key == K_s: state.p1.speed_level = max(1, state.p1.speed_level - 1)
                    
                    if state.game_mode == GAME_MODE_MULTI:
                        if event.key == K_UP: state.p2.speed_level = min(5, state.p2.speed_level + 1)
                        elif event.key == K_DOWN: state.p2.speed_level = max(1, state.p2.speed_level - 1)
                    
                    if event.key == K_r:
                        state.cam_yaw = 0.0
                        state.cam_pitch = 0.0
                
                if state.state_id == STATE_MENU:
                    if event.key in [K_w, K_UP]: state.menu_selection = (state.menu_selection - 1) % 4
                    elif event.key in [K_s, K_DOWN]: state.menu_selection = (state.menu_selection + 1) % 4
                    elif event.key == K_RETURN:
                        if state.menu_selection == 0: state.game_mode, state.state_id = GAME_MODE_SOLO, STATE_DIFFICULTY_SELECT
                        elif state.menu_selection == 1: state.game_mode, state.state_id = GAME_MODE_MULTI, STATE_DIFFICULTY_SELECT
                        elif state.menu_selection == 2: launch_extra_game()
                        elif state.menu_selection == 3: running = False
                
                elif state.state_id == STATE_DIFFICULTY_SELECT:
                    if event.key in [K_w, K_UP]: state.difficulty_selection = (state.difficulty_selection - 1) % 4
                    elif event.key in [K_s, K_DOWN]: state.difficulty_selection = (state.difficulty_selection + 1) % 4
                    elif event.key == K_RETURN:
                        state.current_difficulty = DIFFICULTY_ORDER[state.difficulty_selection]
                        state.reset(); state.state_id = STATE_PLAYING
                    elif event.key == K_ESCAPE: state.state_id = STATE_MENU
                
                elif state.state_id == STATE_PLAYING:
                    if event.key in [K_p, K_ESCAPE]: state.state_id = STATE_PAUSED
                
                elif state.state_id == STATE_PAUSED:
                    if event.key in [K_w, K_UP, K_a, K_LEFT, K_s, K_DOWN, K_d, K_RIGHT]: state.pause_selection = (state.pause_selection - 1) % 3
                    elif event.key == K_RETURN:
                        if state.pause_selection == 0: state.state_id = STATE_PLAYING
                        elif state.pause_selection == 1: 
                            state.reset()
                            state.state_id = STATE_PLAYING
                        else: state.state_id = STATE_MENU
                        if state.snd_win_music: state.snd_win_music.stop()

                elif state.state_id in [STATE_GAMEOVER, STATE_WIN]:
                    if event.key in [K_w, K_UP, K_a, K_LEFT, K_s, K_DOWN, K_d, K_RIGHT]: state.end_screen_selection = 1 - state.end_screen_selection
                    elif event.key == K_RETURN:
                        if state.snd_win_music: state.snd_win_music.stop()
                        if state.end_screen_selection == 0: 
                            state.reset(); state.state_id = STATE_PLAYING
                        else: 
                            state.state_id = STATE_MENU

        update_game(state, real_dt)
        renderer.draw()
        pygame.display.flip()
    pygame.quit()

if __name__ == "__main__":
    main()