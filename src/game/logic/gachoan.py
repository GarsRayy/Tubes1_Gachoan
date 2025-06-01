from typing import Optional, List, Tuple, Dict
import random
from game.logic.base import BaseLogic
from game.models import GameObject, Board, Position
from ..util import get_direction

class GachoanBot(BaseLogic): 
    def __init__(self):
        super().__init__()
        self.goal: Optional[Position] = None

    def distance(self, pos_a: Position, pos_b: Position) -> int:
        return abs(pos_a.x - pos_b.x) + abs(pos_a.y - pos_b.y)

    def get_teleporters(self, board: Board) -> List[GameObject]:
        return [obj for obj in board.game_objects if obj.type == "TeleportGameObject"]

    def distance_with_teleporter(self, start: Position, end: Position, board: Board) -> int:
        teleporters = self.get_teleporters(board)
        direct_dist = self.distance(start, end)

        if len(teleporters) < 2:
            return direct_dist
        
        tp1 = teleporters[0]
        tp2 = teleporters[1]
        dist_via_tp1_entry = self.distance(start, tp1.position) + self.distance(tp2.position, end)
        dist_via_tp2_entry = self.distance(start, tp2.position) + self.distance(tp1.position, end)
        min_teleport_dist = min(dist_via_tp1_entry, dist_via_tp2_entry)
        return min(direct_dist, min_teleport_dist)

    def get_best_teleport_or_target(self, bot_pos: Position, target_dest: Position, board: Board) -> Position:
        teleporters = self.get_teleporters(board)
        dist_direct = self.distance(bot_pos, target_dest)
        best_next_step_target = target_dest
        min_overall_dist = dist_direct

        if len(teleporters) >= 2:
            tp1 = teleporters[0]
            tp2 = teleporters[1]
            dist_via_tp1_entry = self.distance(bot_pos, tp1.position) + self.distance(tp2.position, target_dest)
            if dist_via_tp1_entry < min_overall_dist:
                min_overall_dist = dist_via_tp1_entry
                best_next_step_target = tp1.position
            dist_via_tp2_entry = self.distance(bot_pos, tp2.position) + self.distance(tp1.position, target_dest)
            if dist_via_tp2_entry < min_overall_dist:
                best_next_step_target = tp2.position
        return best_next_step_target

    def get_closest_diamond(self, bot: GameObject, board: Board, red_only: bool = False, blue_only: bool = False) -> Optional[GameObject]:
        diamonds_found: List[GameObject] = []
        MAX_DIAMOND_CAPACITY = getattr(bot.properties, "diamonds_carried_max", 5)
        current_diamonds_held = bot.properties.diamonds
        bot_pos = bot.position

        for d_obj in board.diamonds:
            diamond_points = d_obj.properties.points
            target_this_diamond_type = False
            if red_only:
                if diamond_points == 2: target_this_diamond_type = True
            elif blue_only:
                if diamond_points == 1: target_this_diamond_type = True
            else:
                target_this_diamond_type = True

            if target_this_diamond_type:
                can_hold = False
                if diamond_points == 2 and (current_diamonds_held + 2 <= MAX_DIAMOND_CAPACITY):
                    can_hold = True
                elif diamond_points == 1 and (current_diamonds_held + 1 <= MAX_DIAMOND_CAPACITY):
                    can_hold = True
                if can_hold:
                    diamonds_found.append(d_obj)
        
        if not diamonds_found: return None
        closest_diamond_obj: Optional[GameObject] = None
        min_effective_dist_to_diamond = float('inf')

        for d_obj in diamonds_found:
            effective_dist = self.distance_with_teleporter(bot_pos, d_obj.position, board)
            if effective_dist < min_effective_dist_to_diamond:
                closest_diamond_obj = d_obj
                min_effective_dist_to_diamond = effective_dist
        return closest_diamond_obj

    def get_red_button(self, board: Board) -> Optional[GameObject]:
        for obj in board.game_objects:
            if obj.type == "DiamondButtonGameObject":
                return obj
        return None

    def get_game_status_info(self, bot: GameObject, board: Board) -> Dict:
        """
        Menganalisis status permainan relatif terhadap lawan.
        Membutuhkan `bot.properties.score` untuk berfungsi optimal.
        """
        my_score = getattr(bot.properties, "score", 0)
        highest_opponent_score = 0
        total_bots = len(board.bots)
        
        # Informasi untuk disrupsi red button (sederhana)
        # Cek apakah ada lawan dengan banyak diamond dekat cluster diamond
        opponent_primed_for_big_score = False
        if total_bots > 1:
            for obot in board.bots:
                if obot.id != bot.id:
                    obot_diamonds = getattr(obot.properties, "diamonds", 0)
                    # Jika ada lawan bawa banyak diamond dan dekat dengan >1 diamond lain (indikasi cluster)
                    if obot_diamonds >= 3: # Lawan bawa cukup banyak
                        close_diamonds_to_opponent = 0
                        for diamond_on_board in board.diamonds:
                            if self.distance(obot.position, diamond_on_board.position) <= 3:
                                close_diamonds_to_opponent +=1
                        if close_diamonds_to_opponent >= 2: # Lawan dekat dengan setidaknya 2 diamond
                            opponent_primed_for_big_score = True
                            break # Cukup satu kondisi terpenuhi

        if total_bots > 1:
            for obot in board.bots:
                if obot.id != bot.id:
                    opponent_score = getattr(obot.properties, "score", 0)
                    if opponent_score > highest_opponent_score:
                        highest_opponent_score = opponent_score
        
        am_i_leading = my_score > highest_opponent_score if total_bots > 1 else True
        # Jika tidak ada lawan, atau skor sama, anggap tidak ada lead margin spesifik yang perlu dikejar/diamankan
        lead_margin = my_score - highest_opponent_score if total_bots > 1 and my_score != highest_opponent_score else float('inf')


        return {
            "my_score": my_score,
            "highest_opponent_score": highest_opponent_score,
            "am_i_leading": am_i_leading,
            "lead_margin": lead_margin, # Positif jika unggul, negatif jika tertinggal
            "opponent_primed_for_big_score": opponent_primed_for_big_score,
        }

    def next_move(self, bot: GameObject, board: Board) -> Tuple[int, int]:
        props = bot.properties
        pos = bot.position
        base = props.base
        time_left = getattr(board, "time_left", 999)
        current_diamonds = props.diamonds
        MAX_DIAMOND_CAPACITY = getattr(props, "diamonds_carried_max", 5)

        current_turn_goal_pos: Optional[Position] = None
        game_status = self.get_game_status_info(bot, board)

        # --- STRATEGI PRIORITAS TINGGI ---

        # 1. Greedy by Escape:
        if current_diamonds >= 3:
            for enemy_bot in board.bots:
                if enemy_bot.id != bot.id and self.distance(pos, enemy_bot.position) <= 2:
                    self.goal = self.get_best_teleport_or_target(pos, base, board)
                    return get_direction(pos.x, pos.y, self.goal.x, self.goal.y)

        # 2. V4 Feature: "Mengamankan Poin Kritis" (Secure Critical Points)
        #    Jika unggul tipis, waktu mulai mepet (tapi belum kritis absolut), dan bawa diamond.
        #    Harus dijalankan sebelum "Time Critical & Profitable Return" standar.
        secure_points_time_factor = 1.8 # Coba pulang jika sisa waktu < 1.8x perjalanan ke base
        slim_lead_threshold = MAX_DIAMOND_CAPACITY # Unggul kurang dari satu kali drop penuh
        effective_steps_to_base = self.distance_with_teleporter(pos, base, board)
        safe_time_buffer_profit_return = 4 # Buffer untuk pulang profit standar

        # Cek apakah waktu untuk "mengamankan" sudah tiba, tapi belum masuk waktu "kritis profit"
        is_securing_time_window = (time_left <= effective_steps_to_base * secure_points_time_factor) and \
                                  (time_left > effective_steps_to_base + safe_time_buffer_profit_return)

        if game_status["am_i_leading"] and \
           game_status["lead_margin"] < slim_lead_threshold and \
           current_diamonds >= 1 and \
           is_securing_time_window:
            self.goal = self.get_best_teleport_or_target(pos, base, board)
            # print(f"BOT V4 DEBUG: Securing critical points! Lead: {game_status['lead_margin']}, Time: {time_left}")
            return get_direction(pos.x, pos.y, self.goal.x, self.goal.y)

        # 3. Greedy by Return (Waktu Kritis DAN ADA PROFIT):
        if current_diamonds > 0 and (time_left <= effective_steps_to_base + safe_time_buffer_profit_return):
            self.goal = self.get_best_teleport_or_target(pos, base, board)
            # print(f"BOT V4 DEBUG: Time critical & profitable return. Diamonds: {current_diamonds}, Time Left: {time_left}")
            return get_direction(pos.x, pos.y, self.goal.x, self.goal.y)

        # 4. V3 Feature: "Last Dash Diamond Grab"
        last_dash_max_time_eval = 10 
        min_buffer_last_dash = 1    
        max_direct_dist_dash_diamond = 2 
        if not current_turn_goal_pos and current_diamonds == 0 and (time_left <= last_dash_max_time_eval):
            # ... (Logika Last Dash dari V3, pastikan sudah benar)
            best_last_dash_diamond_obj: Optional[GameObject] = None
            min_total_steps_for_last_dash = float('inf')
            potential_diamonds_for_dash = [
                d for d in board.diamonds if self.distance(pos, d.position) <= max_direct_dist_dash_diamond
            ]
            for d_obj in potential_diamonds_for_dash:
                # ... (pengecekan kapasitas dan perhitungan langkah)
                dist_to_diamond_direct = self.distance(pos, d_obj.position)
                steps_from_diamond_to_base = self.distance_with_teleporter(d_obj.position, base, board)
                total_steps_this_dash = dist_to_diamond_direct + steps_from_diamond_to_base 
                if total_steps_this_dash < min_total_steps_for_last_dash and \
                   (total_steps_this_dash + min_buffer_last_dash <= time_left):
                    min_total_steps_for_last_dash = total_steps_this_dash
                    best_last_dash_diamond_obj = d_obj
            if best_last_dash_diamond_obj:
                current_turn_goal_pos = best_last_dash_diamond_obj.position

        # --- PENETAPAN TUJUAN STRATEGIS (Jika tidak ada override/goal dari atas) ---

        # 5. Greedy by Tackle (Langsung) - V4 Refined Risk/Reward
        if not current_turn_goal_pos:
            # Kurangi agresivitas jika bawa banyak diamond, kecuali skor sangat tertinggal
            can_tackle_aggressively = True
            if current_diamonds >= MAX_DIAMOND_CAPACITY -1 : # Bawa hampir penuh
                # Hanya tackle jika sangat tertinggal (misal, skor < 50% skor lawan tertinggi)
                if game_status["my_score"] < game_status["highest_opponent_score"] * 0.5 or game_status["am_i_leading"]:
                     pass # Boleh tackle jika sangat tertinggal atau sudah unggul (nothing to lose much)
                else: # Bawa banyak, tidak tertinggal jauh, jangan ambil risiko
                    can_tackle_aggressively = False
            
            if can_tackle_aggressively:
                for enemy_bot in board.bots:
                    if enemy_bot.id != bot.id and \
                       self.distance(pos, enemy_bot.position) == 1 and \
                       getattr(enemy_bot.properties, "diamonds", 0) >= 2:
                        if current_diamonds < 2 or getattr(enemy_bot.properties, "diamonds", 0) >= (MAX_DIAMOND_CAPACITY -1) :
                            current_turn_goal_pos = enemy_bot.position 
                            break
        
        # 6. Greedy by Inventory Full:
        if not current_turn_goal_pos:
            if current_diamonds >= MAX_DIAMOND_CAPACITY:
                current_turn_goal_pos = self.get_best_teleport_or_target(pos, base, board)

        # 7. Greedy by Red Button - V4 Smarter Usage
        if not current_turn_goal_pos:
            red_button_obj = self.get_red_button(board)
            if red_button_obj:
                press_button_for_scarcity_or_advantage = False
                # Kondisi dasar dari V3 (diamond langka atau tombol lebih dekat)
                diamonds_on_board_count = len(board.diamonds)
                if diamonds_on_board_count == 0 and current_diamonds < MAX_DIAMOND_CAPACITY:
                     press_button_for_scarcity_or_advantage = True
                elif diamonds_on_board_count < 4 and current_diamonds < MAX_DIAMOND_CAPACITY -1 :
                    press_button_for_scarcity_or_advantage = True
                # ... (bisa tambahkan kondisi V3 lainnya jika relevan)

                press_button_for_disruption = False
                # Kondisi disrupsi: lawan mau skor besar, kita tidak unggul, dan tombol dekat
                dist_to_button_eff = self.distance_with_teleporter(pos, red_button_obj.position, board)
                if game_status["opponent_primed_for_big_score"] and \
                   (not game_status["am_i_leading"] or game_status["lead_margin"] < MAX_DIAMOND_CAPACITY) and \
                   dist_to_button_eff <= 4 : # Tombol harus cukup dekat untuk aksi disrupsi cepat
                    press_button_for_disruption = True

                press_button_when_behind = False
                # Kondisi reset saat tertinggal: skor rendah, diamond sedikit, tombol dekat
                if not game_status["am_i_leading"] and game_status["my_score"] < game_status["highest_opponent_score"] * 0.6 and \
                   diamonds_on_board_count < 6 and \
                   dist_to_button_eff <= 5:
                    press_button_when_behind = True
                
                if press_button_for_disruption or press_button_when_behind or press_button_for_scarcity_or_advantage:
                    current_turn_goal_pos = red_button_obj.position
        
        # 8. Greedy by Tackle (Proaktif/Mendekat) - V4 Refined Risk/Reward
        if not current_turn_goal_pos:
            # Logika agresivitas sama seperti tackle langsung
            can_tackle_proactively = True
            if current_diamonds >= MAX_DIAMOND_CAPACITY - 1: # Bawa hampir penuh
                if game_status["my_score"] < game_status["highest_opponent_score"] * 0.5 or game_status["am_i_leading"]:
                     pass 
                else:
                    can_tackle_proactively = False

            if can_tackle_proactively and current_diamonds < MAX_DIAMOND_CAPACITY - (MAX_DIAMOND_CAPACITY // 2) + 1 : 
                for enemy_bot in board.bots:
                    if enemy_bot.id != bot.id and \
                       self.distance(pos, enemy_bot.position) == 2 and \
                       getattr(enemy_bot.properties, "diamonds", 0) >= 2:
                        current_turn_goal_pos = enemy_bot.position
                        break
        
        # 9. Greedy by Diamond Collection:
        if not current_turn_goal_pos:
            # ... (Logika dari V3 menggunakan get_closest_diamond yang sudah mempertimbangkan teleporter)
            red_diamond_obj = self.get_closest_diamond(bot, board, red_only=True)
            blue_diamond_obj = self.get_closest_diamond(bot, board, blue_only=True)
            # ... (Pemilihan antara merah dan biru berdasarkan jarak efektif dan kapasitas)
            target_diamond_pos: Optional[Position] = None
            if red_diamond_obj and blue_diamond_obj:
                dist_eff_red = self.distance_with_teleporter(pos, red_diamond_obj.position, board)
                dist_eff_blue = self.distance_with_teleporter(pos, blue_diamond_obj.position, board)
                if dist_eff_red <= dist_eff_blue + 2 : 
                    target_diamond_pos = red_diamond_obj.position
                else:
                    target_diamond_pos = blue_diamond_obj.position
            elif red_diamond_obj:
                target_diamond_pos = red_diamond_obj.position
            elif blue_diamond_obj:
                target_diamond_pos = blue_diamond_obj.position
            
            if target_diamond_pos:
                current_turn_goal_pos = target_diamond_pos
            else: 
                if not current_turn_goal_pos:
                     current_turn_goal_pos = self.get_best_teleport_or_target(pos, base, board)

        # 10. Aksi Default:
        if not current_turn_goal_pos:
            current_turn_goal_pos = self.get_best_teleport_or_target(pos, base, board)

        # --- PENYESUAIAN AKHIR & EKSEKUSI ---
        self.goal = current_turn_goal_pos 
        if self.goal != base and self.distance(pos, base) == 1 and current_diamonds > 0:
            self.goal = base
        if not self.goal: self.goal = base 
            
        delta_x, delta_y = get_direction(pos.x, pos.y, self.goal.x, self.goal.y)
        return delta_x, delta_y
