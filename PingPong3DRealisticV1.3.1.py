from ursina import *
import random
import numpy as np

app = Ursina()

# --- USTAWIENIA OKNA I KAMERY ---
window.fps_counter.enabled = False
camera.position = (0, 1.5, -6)
camera.rotation_x = 10

# --- ŚRODOWISKO ---
Entity(model="plane", scale=100, texture="white_cube", texture_scale=(100, 100),
       color=color.light_gray, y=-0.5)
Sky()

# --- STÓŁ ---
table = Entity(model="cube", scale=(2, 0.1, 4), color=color.dark_gray, y=0, z=1)
net = Entity(model="cube", scale=(2.1, 0.3, 0.05), y=0.15, z=1, color=color.white, alpha=0.7)

# --- PALETKI ---
player_paddle = Entity(model="cube", color=color.red, scale=(0.4, 0.4, 0.1), collider="box", y=0.5, z=-1)
ai_paddle = Entity(model="cube", color=color.blue, scale=(0.4, 0.4, 0.1), collider="box", z=3, y=0.5)

# --- PIŁKA ---
ball = Entity(model="sphere", scale=0.15, color=color.orange, collider="sphere", y=0.5)
ball.velocity = Vec3(0,0,0)
ball.spin = Vec3(0,0,0)

# --- FIZYKA ---
gravity = -9.81
air_density = 1.2
drag_coefficient = 0.47
ball_area = np.pi * (ball.scale_x/2)**2
magnus_coeff = 0.0005
paddle_speed = 5
max_speed = 10

# --- OGRANICZENIA OKNA ---
ceiling_y = 2.0
floor_y = table.y + ball.scale_y/2

# --- AI ---
ai_base_speed = 3.5
ai_error_base = 0.3
ai_reaction_time_base = 0.25
ai_timer = 0
ai_target = Vec3(0,0,0)

# --- PUNKTY ---
player_score = 0
ai_score = 0
game_over = False

score_text = Text(text="0 : 0", scale=2, y=0.45)
end_text = Text(text="", scale=3, y=0, color=color.yellow)
end_text.enabled = False

def update_score():
    score_text.text = f"{player_score} : {ai_score}"

def end_game(text):
    global game_over
    game_over = True
    end_text.text = text
    end_text.enabled = True
    invoke(restart_game, delay=3)

def restart_game():
    global player_score, ai_score, game_over
    player_score = 0
    ai_score = 0
    game_over = False
    end_text.enabled = False
    update_score()
    reset_ball()

# --- START PIŁKI BLISKO GRACZA ---
def reset_ball():
    global ai_target
    ai_paddle.position = Vec3(0, 0.5, 3)
    ball.position = Vec3(0, 0.65, -1.5)
    ball.velocity = Vec3(random.uniform(-1,1), 2, 5)
    ball.spin = Vec3(random.uniform(-1,1), random.uniform(-1,1), random.uniform(-1,1))
    ai_target = Vec3(ball.x, ball.y, ai_paddle.z)

reset_ball()
update_score()

# --- FUNKCJE FIZYCZNE ---
def apply_drag(v):
    v_np = np.array([v.x, v.y, v.z])
    speed = np.linalg.norm(v_np)
    if speed == 0:
        return Vec3(0,0,0)
    drag_mag = 0.5 * air_density * drag_coefficient * ball_area * speed**2
    drag = -v_np / speed * drag_mag
    return Vec3(*drag)

def apply_magnus(v, spin):
    v_np = np.array([v.x, v.y, v.z])
    spin_np = np.array([spin.x, spin.y, spin.z])
    magnus = magnus_coeff * np.cross(spin_np, v_np)
    return Vec3(*magnus)

def predict_ball_position():
    if ball.velocity.z == 0:
        return Vec3(ball.x, ball.y, ai_paddle.z)
    t = (ai_paddle.z - ball.z) / ball.velocity.z
    predicted_x = ball.x + ball.velocity.x * t
    predicted_y = ball.y + ball.velocity.y * t + 0.5 * gravity * t**2
    predicted_y = clamp(predicted_y, 0.2, 1.8)
    predicted_x += random.uniform(-ai_error_base, ai_error_base)
    predicted_y += random.uniform(-ai_error_base, ai_error_base)
    return Vec3(predicted_x, predicted_y, ai_paddle.z)

# --- UPDATE ---
def update():
    global player_score, ai_score, ai_timer, ai_target, game_over

    if game_over:
        return

    dt = time.dt

    # --- Sterowanie gracza ---
    target_x = mouse.x * 5
    target_y = max(0.1, (mouse.y * 4) + 1)
    player_paddle.x += clamp(target_x - player_paddle.x, -paddle_speed*dt, paddle_speed*dt)
    player_paddle.y += clamp(target_y - player_paddle.y, -paddle_speed*dt, paddle_speed*dt)
    player_paddle.y = clamp(player_paddle.y, 0.2, 1.8)

    # --- AI ---
    if ball.velocity.z > 0:
        ai_timer -= dt * (0.7 if abs(ball.velocity.x) > 5 or abs(ball.spin.z) > 3 else 1)
        if ai_timer <= 0:
            ai_target = predict_ball_position()
            ai_timer = ai_reaction_time_base + random.uniform(0, 0.1)

        move_vector = ai_target - ai_paddle.position
        max_move_x = ai_base_speed * dt
        max_move_y = (ai_base_speed * 0.9) * dt
        move_vector.x = clamp(move_vector.x, -max_move_x, max_move_x)
        move_vector.y = clamp(move_vector.y, -max_move_y, max_move_y)
        ai_paddle.position += move_vector
        ai_paddle.y = clamp(ai_paddle.y, 0.2, 1.8)

    # --- Kolizje z paletkami ---
    for paddle in [player_paddle, ai_paddle]:
        hit = ball.intersects(paddle)
        if hit.hit:
            direction = 1 if paddle == player_paddle else -1
            delta_y = ball.y - paddle.y
            delta_x = ball.x - paddle.x
            ball.velocity.z = 7 * direction
            ball.velocity.y = clamp(2 + delta_y*3, 2, 3)
            ball.velocity.x += delta_x * 3
            ball.spin += Vec3(delta_y*2, 0, delta_x*2)

    # --- Fizyka piłki ---
    v_np = np.array([ball.velocity.x, ball.velocity.y, ball.velocity.z])
    v_np += np.array([0, gravity, 0]) * dt
    drag = np.array([apply_drag(ball.velocity).x, apply_drag(ball.velocity).y, apply_drag(ball.velocity).z])
    magnus = np.array([apply_magnus(ball.velocity, ball.spin).x, apply_magnus(ball.velocity, ball.spin).y, apply_magnus(ball.velocity, ball.spin).z])
    v_np += drag * dt + magnus * dt
    if np.linalg.norm(v_np) > max_speed:
        v_np = v_np / np.linalg.norm(v_np) * max_speed
    ball.velocity = Vec3(*v_np)
    ball.position += ball.velocity * dt

    # --- Odbicie od stołu i sufitu ---
    if ball.y - ball.scale_y/2 < floor_y:
        ball.y = floor_y + ball.scale_y/2
        ball.velocity.y = abs(ball.velocity.y) * 0.8
    if ball.y + ball.scale_y/2 > ceiling_y:
        ball.y = ceiling_y - ball.scale_y/2
        ball.velocity.y = -abs(ball.velocity.y) * 0.8

    # --- Punktacja i reset ---
    half_width = table.scale_x / 2
    half_depth = table.scale_z / 2
    table_top = table.y + table.scale_y/2
    table_bottom = table.y - table.scale_y/2

    if ball.z < -3:
        global ai_score
        ai_score += 1
        update_score()
        reset_ball()
        return

    if ball.z > 5:
        global player_score
        player_score += 1
        update_score()
        reset_ball()
        return

    if (ball.x < table.x - half_width or ball.x > table.x + half_width or
        ball.y - ball.scale_y/2 < table_bottom or ball.y + ball.scale_y/2 > ceiling_y):
        reset_ball()
        return

    # --- Zwycięstwo ---
    if player_score >= 7:
        end_game("Wygrałeś!")
    if ai_score >= 7:
        end_game("Przegrałeś!")

mouse.visible = False
app.run()