import app
import random
import json
from events.input import Buttons, BUTTON_TYPES
from tildagonos import tildagonos
from system.eventbus import eventbus
from system.patterndisplay.events import PatternDisable, PatternEnable

TEST_MODE = False

class TildaJump(app.App):
    def __init__(self):
        self.button_states = Buttons(self)
        self.state = 'title'
        self.twinkle_timer = 0.0
        self.twinkle_led = 1
        self.twinkle_led2 = 2
        self.twinkle_brightness = 0.0
        self.high_score = self._load_high_score()
        self.last_score = 0
        eventbus.emit(PatternDisable())

    def _load_high_score(self):
        try:
            with open('tildajump_save.json', 'r') as f:
                data = json.load(f)
                return data.get('high_score', 0)
        except Exception:
            return 0

    def _save_high_score(self, score):
        try:
            with open('tildajump_save.json', 'w') as f:
                json.dump({'high_score': score}, f)
        except Exception:
            pass

    def reset_game(self):
        self.robot_radius = 12.0
        self.robot_speed = 0.25

        self.robot_x = 0.0
        self.robot_target_x = 0.0
        self.robot_vx = 0.0
        self.robot_y = 60.0 + self.robot_radius * 2
        self.robot_vy = 0.0

        self.gravity = 0.0003
        self.jump_velocity = -0.55

        self.score = 0
        self.world_scroll = 0.0
        self.moon_y = -180.0
        self.moon_scrolling = False
        self.planets = self._generate_planets()
        self.clouds = []
        self.stars = []
        for _ in range(3):
            self._spawn_cloud()

        self.platforms = []
        self.generate_initial_platforms()

        self.robot_vy = self.jump_velocity
        self.state = 'playing'

    def make_platform(self, y):
        if TEST_MODE:
            return {'x': 0.0, 'y': y, 'w': 60.0, 'h': 8.0, 'color': (0.2, 0.9, 0.2)}
        w = random.uniform(35.0, 70.0)
        x = random.uniform(-110.0 + w / 2, 110.0 - w / 2)
        color = (
            random.uniform(0.2, 0.9),
            random.uniform(0.4, 1.0),
            random.uniform(0.2, 0.7),
        )
        return {'x': x, 'y': y, 'w': w, 'h': 8.0, 'color': color}

    def generate_initial_platforms(self):
        self.platforms.append({
            'x': 0.0, 'y': self.robot_y,
            'w': 60.0, 'h': 8.0, 'color': (0.2, 0.9, 0.2)
        })
        y = self.robot_y
        spacing = 80.0 if TEST_MODE else None
        for _ in range(12):
            y -= spacing if TEST_MODE else random.uniform(40.0, 80.0)
            self.platforms.append(self.make_platform(y))

    def _generate_planets(self):
        moon_r = 90.0
        min_r  = moon_r * 0.5
        max_r  = moon_r * 2.5
        planets = []
        xs = [-60.0, 60.0, -40.0, 75.0, -75.0, 35.0]
        palettes = [
            (0.8, 0.3, 0.1),
            (0.2, 0.5, 0.8),
            (0.6, 0.2, 0.6),
            (0.1, 0.6, 0.3),
            (0.7, 0.6, 0.1),
            (0.5, 0.1, 0.2),
        ]
        styles = ['stripes', 'spots', 'rings', 'stripes', 'spots', 'rings']
        random.shuffle(styles)
        trigger = 900
        for i in range(6):
            r   = random.uniform(min_r, max_r)
            cx  = xs[i % len(xs)] + random.uniform(-10.0, 10.0)
            col = palettes[i % len(palettes)]
            dark = (col[0] * 0.55, col[1] * 0.55, col[2] * 0.55)
            style = styles[i % len(styles)]
            details = []
            if style == 'stripes':
                n = random.randint(3, 6)
                for j in range(n):
                    dy = -r + (2 * r / (n + 1)) * (j + 1)
                    details.append(dy)
            elif style == 'spots':
                n = random.randint(3, 6)
                for _ in range(n):
                    details.append({
                        'dx': random.uniform(-r * 0.6, r * 0.6),
                        'dy': random.uniform(-r * 0.6, r * 0.6),
                        'r':  random.uniform(r * 0.08, r * 0.18),
                    })
            elif style == 'rings':
                import math
                angle = random.uniform(0.3, 0.7)
                details = {'radii': [r * 1.4, r * 1.75], 'angle': angle}
            planets.append({
                'cx': cx, 'y': -180.0,
                'r': r, 'col': col, 'dark': dark,
                'style': style, 'details': details,
                'trigger': trigger, 'scrolling': False, 'done': False,
            })
            trigger += 400
        return planets

    def _spawn_cloud(self):
        circles = []
        for _ in range(random.randint(4, 6)):
            circles.append({
                'dx': random.uniform(-18.0, 18.0),
                'dy': random.uniform(-6.0,   6.0),
                'r':  random.uniform(10.0,  16.0),
            })
        vx = random.uniform(-0.05, 0.05)
        if abs(vx) < 0.015:
            vx = 0.015
        self.clouds.append({
            'x':      random.uniform(-90.0, 90.0),
            'y':      -130.0,
            'vx':     vx,
            'opacity': 0.0,
            'circles': circles,
        })

    def _spawn_star(self):
        self.stars.append({
            'x':      random.uniform(-118.0, 118.0),
            'y':      -130.0,
            'opacity': 0.0,
            'target': random.uniform(0.5, 0.8),
        })

    def update(self, delta):
        left    = self.button_states.get(BUTTON_TYPES["LEFT"])
        right   = self.button_states.get(BUTTON_TYPES["RIGHT"])
        cancel  = self.button_states.get(BUTTON_TYPES["CANCEL"])
        confirm = self.button_states.get(BUTTON_TYPES["CONFIRM"])
        self.button_states.clear()

        if self.state == 'title':
            if cancel:
                eventbus.emit(PatternEnable())
                self.minimise()
            if confirm:
                self.reset_game()
            self._update_leds(delta)
            return

        if cancel:
            self.state = 'title'
            return

        step     = self.robot_speed * 80
        lerp_speed = 0.015

        if left:
            self.robot_target_x -= step
        if right:
            self.robot_target_x += step

        max_x = 120.0 - self.robot_radius
        if self.robot_target_x < -max_x:
            self.robot_target_x = -max_x
        if self.robot_target_x > max_x:
            self.robot_target_x = max_x

        diff = self.robot_target_x - self.robot_x
        move = diff * lerp_speed * delta
        if abs(move) >= abs(diff):
            self.robot_x = self.robot_target_x
        else:
            self.robot_x += move

        if self.robot_x < -120.0:
            self.robot_x = 120.0
            self.robot_target_x = 120.0
        if self.robot_x > 120.0:
            self.robot_x = -120.0
            self.robot_target_x = -120.0

        self.robot_vy += self.gravity * delta
        self.robot_y  += self.robot_vy * delta

        scroll_threshold = -20.0
        if self.robot_y < scroll_threshold:
            shift = scroll_threshold - self.robot_y
            self.world_scroll += shift
            self.score = int(self.world_scroll / 10) * (3 if TEST_MODE else 1)
            for p in self.platforms:
                p['y'] += shift
            for c in self.clouds:
                c['y'] += shift
            for s in self.stars:
                s['y'] += shift
            if self.score >= 500 and not self.moon_scrolling:
                self.moon_scrolling = True
                self.moon_y = -(120.0 + 90.0)
            if self.moon_scrolling and self.moon_y < 400.0:
                self.moon_y += shift
            for pl in self.planets:
                if not pl['done']:
                    if self.score >= pl['trigger'] and not pl['scrolling']:
                        pl['scrolling'] = True
                        pl['y'] = -(120.0 + pl['r'])
                    if pl['scrolling']:
                        pl['y'] += shift
                        if pl['y'] - pl['r'] > 400.0:
                            pl['done'] = True
            self.robot_y = scroll_threshold

        self.platforms = [p for p in self.platforms if p['y'] < 130.0]

        if self.platforms:
            top_y = min(p['y'] for p in self.platforms)
        else:
            top_y = self.robot_y
        while len(self.platforms) < 14:
            spacing = random.uniform(40.0, 80.0)
            top_y -= spacing
            self.platforms.append(self.make_platform(top_y))

        if self.robot_vy > 0:
            robot_bottom_prev = self.robot_y - self.robot_vy * delta
            robot_bottom      = self.robot_y
            for p in self.platforms:
                plat_top   = p['y']
                plat_left  = p['x'] - p['w'] / 2
                plat_right = p['x'] + p['w'] / 2
                if (robot_bottom_prev <= plat_top and
                        robot_bottom >= plat_top and
                        self.robot_x + self.robot_radius * 0.8 > plat_left and
                        self.robot_x - self.robot_radius * 0.8 < plat_right):
                    self.robot_vy = self.jump_velocity
                    self.robot_y  = plat_top
                    break

        if self.robot_y > 130.0:
            self.last_score = self.score
            if self.score > self.high_score:
                self.high_score = self.score
                self._save_high_score(self.score)
            self.reset_game()
            self.state = 'title'

        if 240 <= self.score < 400:
            target_opacity = min(1.0, (self.score - 240) / 20.0) * 0.65
            for c in self.clouds:
                c['x'] += c['vx'] * delta
                if c['x'] > 150.0:
                    c['x'] = -150.0
                elif c['x'] < -150.0:
                    c['x'] = 150.0
                if c['opacity'] < target_opacity:
                    c['opacity'] = min(target_opacity, c['opacity'] + 0.0002 * delta)
            self.clouds = [c for c in self.clouds if c['y'] < 140.0]
            if self.score >= 250 and len(self.clouds) < 5:
                self._spawn_cloud()
        elif self.score >= 400:
            for c in self.clouds:
                c['x'] += c['vx'] * delta
                c['opacity'] = max(0.0, c['opacity'] - 0.0001 * delta)
            self.clouds = [c for c in self.clouds if c['y'] < 140.0 and c['opacity'] > 0]

        if self.score >= 400:
            if self.score < 450:
                target_opacity = (self.score - 400) / 50.0 * 0.7
            else:
                target_opacity = 1.0
            for s in self.stars:
                desired = s['target'] * target_opacity
                if s['opacity'] < desired:
                    s['opacity'] = min(desired, s['opacity'] + 0.0003 * delta)
            self.stars = [s for s in self.stars if s['y'] < 140.0]
            if len(self.stars) < 40:
                self._spawn_star()

        self._update_leds(delta)

    def _update_leds(self, delta):
        try:
            if self.state == 'title':
                for i in range(1, 13):
                    tildagonos.leds[i] = (0, 20, 0)
                tildagonos.leds.write()
                return

            if self.score < 400:
                fade = max(0.0, min(1.0, 1.0 - self.score / 400.0))
                g = max(0, min(255, int(115 * fade)))
                b = max(0, min(255, int(191 * fade)))
                if g < 4 and b < 4:
                    for i in range(1, 13):
                        tildagonos.leds[i] = (0, 0, 0)
                else:
                    for i in range(1, 13):
                        tildagonos.leds[i] = (0, g, b)
            else:
                base = 6
                for i in range(1, 13):
                    tildagonos.leds[i] = (base, base, base)

                self.twinkle_timer -= delta
                if self.twinkle_timer <= 0:
                    self.twinkle_timer = random.uniform(1500.0, 3000.0)
                    self.twinkle_led = random.randint(1, 12)
                    self.twinkle_led2 = random.randint(1, 11)
                    if self.twinkle_led2 >= self.twinkle_led:
                        self.twinkle_led2 += 1
                    self.twinkle_brightness = 0.0

                self.twinkle_brightness = min(1.0, self.twinkle_brightness + 0.001 * delta)

                v1 = max(base, min(255, int(25 + 230 * self.twinkle_brightness)))
                v2 = max(base, min(127, int(25 + 102 * self.twinkle_brightness)))

                tildagonos.leds[self.twinkle_led]  = (v1, v1, v1)
                tildagonos.leds[self.twinkle_led2] = (v2, v2, v2)

            tildagonos.leds.write()
        except Exception:
            pass

    def _draw_title(self, ctx):
        # Dark green background (full screen, not shifted)
        ctx.rgb(0.05, 0.35, 0.05).rectangle(-120, -120, 240, 240).fill()

        # Shift everything else down 10px
        ctx.translate(0, 10)

        # Title
        ctx.rgb(0.85, 0.8, 0.0)
        ctx.font_size = 28
        title = "TildaJump"
        ctx.move_to(-ctx.text_width(title) / 2, -82).text(title)

        # Subtitle
        ctx.rgb(1.0, 1.0, 1.0)
        ctx.font_size = 14
        for i, line in enumerate(["This is Chip. Help them", "Explore space by jumping!"]):
            ctx.move_to(-ctx.text_width(line) / 2, -60 + i * 18).text(line)

        # Chip character
        s = 16.0
        bx = -s
        by = -35.0
        ctx.rgb(1.0, 0.85, 0.0).rectangle(bx, by, s * 2, s * 2).fill()
        eye_size = s * 0.22
        eye_y = by + s * 0.35
        ctx.rgb(0.0, 0.0, 0.0).rectangle(bx + s * 0.25, eye_y, eye_size, eye_size).fill()
        ctx.rgb(0.0, 0.0, 0.0).rectangle(bx + s * 1.05 - eye_size, eye_y, eye_size, eye_size).fill()

        # Controls
        ctx.rgb(1.0, 1.0, 1.0)
        ctx.font_size = 13
        for i, line in enumerate(["Left - Move Left", "Right - Move Right"]):
            ctx.move_to(-ctx.text_width(line) / 2, 14 + i * 16).text(line)

        # High score and last score
        if self.high_score > 0:
            ctx.rgb(1.0, 0.85, 0.0)
            ctx.font_size = 15
            hs_text = "Best: " + str(self.high_score)
            ctx.move_to(-ctx.text_width(hs_text) / 2, 48).text(hs_text)
        if self.last_score > 0:
            ctx.rgb(0.8, 0.8, 0.8)
            ctx.font_size = 13
            ls_text = "Last: " + str(self.last_score)
            ctx.move_to(-ctx.text_width(ls_text) / 2, 63).text(ls_text)

        # Confirm prompt
        ctx.font_size = 15
        ctx.rgb(0.85, 0.8, 0.0)
        prompt = "Confirm to Start"
        ctx.move_to(-ctx.text_width(prompt) / 2, 80).text(prompt)

    def draw(self, ctx):
        ctx.save()

        if self.state == 'title':
            self._draw_title(ctx)
            ctx.restore()
            return

        t1 = max(0.0, min(1.0, (self.score - 400) / 50.0))
        bg_r = 0.3  * (1.0 - t1)
        bg_g = 0.6  * (1.0 - t1)
        bg_b = 1.0  * (1.0 - t1)
        ctx.rgb(bg_r, bg_g, bg_b).rectangle(-120, -120, 240, 240).fill()

        for s in self.stars:
            if s['opacity'] > 0:
                ctx.rgba(1.0, 1.0, 1.0, s['opacity'])
                ctx.rectangle(s['x'], s['y'], 1.5, 1.5).fill()

        for pl in self.planets:
            if not pl['scrolling'] or pl['done']:
                continue
            py  = pl['y']
            pr  = pl['r']
            pcx = pl['cx']
            if py + pr < -500.0 or py - pr > 400.0:
                continue
            pl_start = -(120.0 + pr)
            op = 0.6 + 0.4 * max(0.0, min(1.0, 1.0 - (py / pl_start)))
            r, g, b = pl['col']
            dr, dg, db = pl['dark']

            ctx.save()
            ctx.rgba(r, g, b, op)
            ctx.begin_path()
            ctx.move_to(pcx + pr, py)
            ctx.arc(pcx, py, pr, 0, 6.2832, 0)
            ctx.fill()
            ctx.restore()

            if pl['style'] == 'stripes':
                stripe_h = max(2.0, pr * 0.12)
                for dy in pl['details']:
                    chord = (pr * pr - dy * dy)
                    if chord < 0:
                        continue
                    import math
                    hw = math.sqrt(chord)
                    ctx.save()
                    ctx.rgba(dr, dg, db, op * 0.7)
                    ctx.rectangle(pcx - hw, py + dy - stripe_h * 0.5, hw * 2, stripe_h).fill()
                    ctx.restore()

            elif pl['style'] == 'spots':
                for spot in pl['details']:
                    ctx.save()
                    ctx.rgba(dr, dg, db, op * 0.8)
                    ctx.begin_path()
                    ctx.move_to(pcx + spot['dx'] + spot['r'], py + spot['dy'])
                    ctx.arc(pcx + spot['dx'], py + spot['dy'], spot['r'], 0, 6.2832, 0)
                    ctx.fill()
                    ctx.restore()

            elif pl['style'] == 'rings':
                import math
                angle = pl['details']['angle']
                for ring_r in pl['details']['radii']:
                    ring_thickness = pr * 0.15
                    ctx.save()
                    ctx.rgba(dr, dg, db, op * 0.7)
                    ctx.translate(pcx, py)
                    ctx.rotate(angle)
                    ctx.scale(1.0, 0.28)
                    ctx.begin_path()
                    ctx.move_to(ring_r + ring_thickness, 0)
                    ctx.arc(0, 0, ring_r + ring_thickness, 0, 6.2832, 0)
                    ctx.fill()
                    ctx.rgba(r, g, b, op)
                    ctx.begin_path()
                    ctx.move_to(ring_r - ring_thickness, 0)
                    ctx.arc(0, 0, ring_r - ring_thickness, 0, 6.2832, 0)
                    ctx.fill()
                    ctx.restore()

        moon_screen_y = self.moon_y
        if self.moon_scrolling and moon_screen_y < 400.0:
            moon_start = -(120.0 + 90.0)
            moon_opacity = 0.6 + 0.4 * max(0.0, min(1.0, 1.0 - (moon_screen_y / moon_start)))
            moon_r  = 90.0
            moon_cx = 50.0
            craters = [
                (-30.0, -25.0, 17.0),
                ( 25.0,  15.0, 13.0),
                (-12.0,  38.0, 10.0),
                ( 42.0, -35.0,  9.0),
                (-48.0,  20.0,  8.0),
                ( 12.0, -55.0, 11.0),
                ( 52.0,  30.0,  7.0),
                (-20.0,  55.0,  6.0),
            ]
            ctx.save()
            ctx.rgba(0.28, 0.26, 0.05, moon_opacity)
            ctx.begin_path()
            ctx.move_to(moon_cx + moon_r, moon_screen_y)
            ctx.arc(moon_cx, moon_screen_y, moon_r, 0, 6.2832, 0)
            ctx.fill()
            ctx.restore()
            for dx, dy, cr in craters:
                ctx.save()
                ctx.rgba(0.18, 0.16, 0.02, moon_opacity)
                ctx.begin_path()
                ctx.move_to(moon_cx + dx + cr, moon_screen_y + dy)
                ctx.arc(moon_cx + dx, moon_screen_y + dy, cr, 0, 6.2832, 0)
                ctx.fill()
                ctx.restore()

        for p in self.platforms:
            r, g, b = p['color']
            ctx.rgb(r, g, b).rectangle(
                p['x'] - p['w'] / 2, p['y'],
                p['w'], p['h']
            ).fill()

        for c in self.clouds:
            if c['opacity'] > 0:
                for circle in c['circles']:
                    cx = c['x'] + circle['dx']
                    cy = c['y'] + circle['dy']
                    r  = circle['r']
                    ctx.save()
                    ctx.rgba(1.0, 1.0, 1.0, c['opacity'])
                    ctx.begin_path()
                    ctx.move_to(cx + r, cy)
                    ctx.arc(cx, cy, r, 0, 6.2832, 0)
                    ctx.fill()
                    ctx.restore()

        s = self.robot_radius
        bx = self.robot_x - s
        by = self.robot_y - s * 2

        ctx.rgb(1.0, 0.85, 0.0).rectangle(bx, by, s * 2, s * 2).fill()

        eye_size = s * 0.28
        eye_y    = by + s * 0.3
        ctx.rgb(0.0, 0.0, 0.0).rectangle(bx + s * 0.2,                    eye_y, eye_size, eye_size).fill()
        ctx.rgb(0.0, 0.0, 0.0).rectangle(bx + s * 1.0 - eye_size * 0.5,  eye_y, eye_size, eye_size).fill()

        ctx.rgb(1.0, 1.0, 1.0)
        ctx.font_size = 16
        score_text = "Score: " + str(self.score)
        tw = ctx.text_width(score_text)
        ctx.move_to(-tw / 2, -100).text(score_text)

        ctx.restore()

__app_export__ = TildaJump
