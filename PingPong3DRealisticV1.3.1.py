from ursina import *
from ursina.prefabs.trail_renderer import TrailRenderer  # Import smugi
import random
import numpy as np

app = Ursina()

# --- USTAWIENIA OKNA I KAMERY ---
window.fps_counter.enabled = False
camera.position = (0, 1.5, -6)
camera.rotation_x = 10

# --- ŚRODOWISKO ---
Entity(
    model="plane",
    scale=100,
    texture="white_cube",
    texture_scale=(100, 100),
    color=color.light_gray,
    y=-0.5,
)
Sky()

# --- STÓŁ ---
table = Entity(model="cube", scale=(2, 0.1, 4), color=color.dark_gray, y=0, z=1)
net = Entity(
    model="cube",
    scale=(2.1, 0.3, 0.05),
    y=0.15,
    z=1,
    color=color.white,
    alpha=0.7,
    collider="box",
)

# --- PALETKI ---
player_paddle = Entity(
    model="cube", color=color.red, scale=(0.4, 0.4, 0.1), collider="box", y=0.5, z=-1
)
ai_paddle = Entity(
    model="cube", color=color.blue, scale=(0.4, 0.4, 0.1), collider="box", z=3, y=0.5
)

# --- PIŁKA ---
ball = Entity(model="sphere", scale=0.15, color=color.orange, collider="sphere", y=0.5)
ball.velocity = Vec3(0, 0, 0)
ball.spin = Vec3(0, 0, 0)

# --- SMUGA (TRAIL) ---
# size=[szerokość_startowa, szerokość_końcowa]
ball_trail = TrailRenderer(
    parent=ball,
    size=[0.1, 0.0], 
    segments=12,
    min_spacing=0.05,
    color=color.orange,
    alpha=0.6
)

# --- FIZYKA ---
gravity = -9.81
air_density = 1.2
drag_coefficient = 0.47
ball_area = np.pi * (ball.scale_x / 2) ** 2
magnus_coeff = 0.0008
paddle_speed = 5
max_speed = 15

# --- OGRANICZENIA ---
ceiling_y = 2.0
floor_y = table.y + 0.05

# --- AI ---
ai_base_speed = 4.0
ai_error_base = 0.25
ai_reaction_time_base = 0.2
ai_timer = 0
ai_target = Vec3(0, 0, 0)

# --- PUNKTY ---
player_score = 0
ai_score = 0
game_over = False
score_text = Text(text="0 : 0", scale=2, y=0.45, origin=(0,0))
end_text = Text(text="", scale=3, y=0, color=color.yellow, origin=(0,0))
end_text.enabled = False


# --- FUNKCJE GRY ---
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


def reset_ball():
    global ai_target
    # Czyścimy starą smugę przed resetem, żeby nie "strzeliła" przez cały stół
    if hasattr(ball_trail, 'renderer'):
        ball_trail.renderer.model.path = [ball.world_position for i in range(2)]
    
    ai_paddle.position = Vec3(0, 0.5, 3)
    ball.position = Vec3(0, 0.65, -1.5)
    ball.velocity = Vec3(random.uniform(-1, 1), 3.0, 5.0)
    ball.spin = Vec3(
        random.uniform(-2, 2), random.uniform(-2, 2), random.uniform(-1, 1)
    )
    ai_target = Vec3(ball.x, ball.y, ai_paddle.z)
    player_paddle.prev_pos = Vec3(player_paddle.position)
    ai_paddle.prev_pos = Vec3(ai_paddle.position)


# --- MECHANIKA FIZYKI ---
def apply_drag(v):
    speed = v.length()
    if speed == 0:
        return Vec3(0, 0, 0)
    drag_mag = 0.5 * air_density * drag_coefficient * ball_area * speed**2
    return -v.normalized() * drag_mag


def apply_magnus(v, spin):
    return Vec3(*np.cross([spin.x, spin.y, spin.z], [v.x, v.y, v.z])) * magnus_coeff


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

    # Sterowanie gracza
    target_x = mouse.x * 5
    target_y = max(0.1, (mouse.y * 4) + 1)
    
    # Obliczanie prędkości paletki (do nadawania rotacji)
    current_player_vel = (Vec3(target_x, target_y, player_paddle.z) - player_paddle.position) / dt
    
    player_paddle.x += clamp(target_x - player_paddle.x, -paddle_speed * dt, paddle_speed * dt)
    player_paddle.y += clamp(target_y - player_paddle.y, -paddle_speed * dt, paddle_speed * dt)
    player_paddle.y = clamp(player_paddle.y, 0.2, 1.8)

    # AI
    ai_vel = Vec3(0,0,0)
    if ball.velocity.z > 0:
        ai_timer -= dt
        if ai_timer <= 0:
            ai_target = predict_ball_position()
            ai_timer = ai_reaction_time_base + random.uniform(0, 0.1)

        move_vector = ai_target - ai_paddle.position
        max_move = ai_base_speed * dt
        if move_vector.length() > max_move:
            move_vector = move_vector.normalized() * max_move
        
        old_ai_pos = Vec3(ai_paddle.position)
        ai_paddle.position += move_vector
        ai_paddle.y = clamp(ai_paddle.y, 0.2, 1.8)
        ai_vel = (ai_paddle.position - old_ai_pos) / dt

    # Kolizje z paletkami
    for paddle, vel in [(player_paddle, current_player_vel), (ai_paddle, ai_vel)]:
        hit = ball.intersects(paddle)
        if hit.hit:
            delta_y = ball.y - paddle.y
            delta_x = ball.x - paddle.x
            ball.velocity.z *= -0.95
            ball.velocity.x += delta_x * 2 + 0.3 * vel.x
            ball.velocity.y += delta_y * 2 + 0.3 * vel.y
            
            # Nadawanie rotacji przy uderzeniu
            ball.spin += Vec3(delta_y * 3 + vel.y, 0.5 * vel.x + delta_x * 2, delta_x * 2)
            
            if ball.velocity.length() > max_speed:
                ball.velocity = ball.velocity.normalized() * max_speed
            
            # Odsunięcie piłki, by uniknąć podwójnej kolizji
            if paddle == player_paddle:
                ball.z = paddle.z + 0.15
            else:
                ball.z = paddle.z - 0.15

    # Fizyka piłki (Aerodynamika + Grawitacja)
    ball.velocity += Vec3(0, gravity, 0) * dt
    ball.velocity += apply_drag(ball.velocity) * dt
    ball.velocity += apply_magnus(ball.velocity, ball.spin) * dt
    ball.position += ball.velocity * dt

    # Kolizja z siatką
    if ball.intersects(net).hit:
        ball.velocity.z *= -0.5
        ball.velocity.x *= 0.5
        ball.spin *= 0.8
        ball.z = net.z + (0.1 if ball.velocity.z > 0 else -0.1)

    # Odbicia od stołu
    if ball.y - 0.075 < floor_y and abs(ball.x) < table.scale_x/2 and abs(ball.z - 1) < table.scale_z/2:
        ball.y = floor_y + 0.075
        ball.velocity.y = abs(ball.velocity.y) * 0.85
        # Tu można dodać wpływ rotacji na odbicie, by było jeszcze trudniej!

    # Punktacja
    if ball.z < -3.5:
        ai_score += 1
        update_score()
        reset_ball()
    elif ball.z > 5.5:
        player_score += 1
        update_score()
        reset_ball()
    
    # Reset przy wypadnięciu poza stół
    if ball.y < -1:
        reset_ball()

    if player_score >= 7: end_game("Wygrałeś!")
    if ai_score >= 7: end_game("Przegrałeś!")

mouse.visible = False
reset_ball()
update_score()
app.run()
