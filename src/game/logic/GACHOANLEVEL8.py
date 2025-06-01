from typing import Optional, List, Tuple
import random
from game.logic.base import BaseLogic
from game.models import GameObject, Board, Position
from ..util import get_direction

class GACHOANLEVEL8(BaseLogic):
    def __init__(self):
        """
        Inisialisasi bot GACHOANLEVEL8.
        """
        super().__init__()
        self.goal: Optional[Position] = None

    def distance(self, pos_a: Position, pos_b: Position) -> int:
        """
        Menghitung jarak Manhattan antara dua posisi.
        """
        return abs(pos_a.x - pos_b.x) + abs(pos_a.y - pos_b.y)

    def get_teleporters(self, board: Board) -> List[GameObject]:
        """
        Mendapatkan semua objek teleporter di board.
        Sesuai PDF, diasumsikan selalu ada 2 teleporter yang saling terhubung.
        """
        return [obj for obj in board.game_objects if obj.type == "TeleportGameObject"]

    def distance_with_teleporter(self, start: Position, end: Position, board: Board) -> int:
        """
        Menghitung jarak terpendek antara start dan end, mempertimbangkan penggunaan satu pasang teleporter.
        """
        teleporters = self.get_teleporters(board)
        direct_dist = self.distance(start, end)

        if len(teleporters) < 2:
            # Jika tidak ada pasangan teleporter yang valid, kembalikan jarak langsung
            return direct_dist

        # Asumsi dari PDF: "Terdapat 2 teleporter yang saling terhubung satu sama lain."
        # tp1 dan tp2 adalah dua teleporter yang membentuk pasangan.
        tp1 = teleporters[0]
        tp2 = teleporters[1]

        # Opsi 1: Masuk melalui tp1, keluar di tp2, lalu ke 'end'
        dist_via_tp1_entry = self.distance(start, tp1.position) + self.distance(tp2.position, end)
        
        # Opsi 2: Masuk melalui tp2, keluar di tp1, lalu ke 'end'
        dist_via_tp2_entry = self.distance(start, tp2.position) + self.distance(tp1.position, end)
        
        min_teleport_dist = min(dist_via_tp1_entry, dist_via_tp2_entry)
        
        return min(direct_dist, min_teleport_dist)

    def get_best_teleport_or_target(self, bot_pos: Position, target_dest: Position, board: Board) -> Position:
        """
        Menentukan posisi langkah berikutnya (bisa jadi teleporter masuk atau target_dest itu sendiri)
        untuk mencapai target_dest dengan rute tercepat, mempertimbangkan teleporter.
        Mengembalikan posisi teleporter masuk yang optimal jika lebih cepat, atau target_dest jika tidak.
        """
        teleporters = self.get_teleporters(board)
        
        dist_direct = self.distance(bot_pos, target_dest)
        best_next_step_target = target_dest # Awalnya, asumsikan jalur langsung adalah yang terbaik
        min_overall_dist = dist_direct

        if len(teleporters) >= 2:
            tp1 = teleporters[0]
            tp2 = teleporters[1]

            # Jalur via tp1 sebagai pintu masuk
            dist_via_tp1_entry = self.distance(bot_pos, tp1.position) + self.distance(tp2.position, target_dest)
            if dist_via_tp1_entry < min_overall_dist:
                min_overall_dist = dist_via_tp1_entry
                best_next_step_target = tp1.position # Tujuan adalah mencapai teleporter masuk ini

            # Jalur via tp2 sebagai pintu masuk
            dist_via_tp2_entry = self.distance(bot_pos, tp2.position) + self.distance(tp1.position, target_dest)
            if dist_via_tp2_entry < min_overall_dist:
                # min_overall_dist = dist_via_tp2_entry # Tidak perlu update min_overall_dist lagi jika hanya mencari target
                best_next_step_target = tp2.position # Tujuan adalah mencapai teleporter masuk ini
        
        return best_next_step_target

    def get_closest_diamond(self, bot: GameObject, board: Board, red_only: bool = False, blue_only: bool = False) -> Optional[GameObject]:
        """
        Mencari diamond terdekat yang bisa diambil bot, MEMPERTIMBANGKAN TELEPORTER untuk jarak.
        """
        diamonds_found: List[GameObject] = []
        # Gunakan properti bot jika ada, fallback ke 5 jika tidak ada
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
            else: # Cari semua jenis jika tidak ada filter spesifik
                target_this_diamond_type = True

            if target_this_diamond_type:
                can_hold = False
                if diamond_points == 2 and (current_diamonds_held + 2 <= MAX_DIAMOND_CAPACITY):
                    can_hold = True
                elif diamond_points == 1 and (current_diamonds_held + 1 <= MAX_DIAMOND_CAPACITY):
                    can_hold = True
                
                if can_hold:
                    diamonds_found.append(d_obj)
        
        if not diamonds_found:
            return None

        closest_diamond_obj: Optional[GameObject] = None
        min_effective_dist_to_diamond = float('inf')

        for d_obj in diamonds_found:
            # MENGGUNAKAN distance_with_teleporter UNTUK MENGHITUNG JARAK EFEKTIF
            effective_dist = self.distance_with_teleporter(bot_pos, d_obj.position, board)
            
            if effective_dist < min_effective_dist_to_diamond:
                closest_diamond_obj = d_obj
                min_effective_dist_to_diamond = effective_dist
        
        return closest_diamond_obj

    def get_red_button(self, board: Board) -> Optional[GameObject]:
        """Mendapatkan objek Tombol Merah (Diamond Button) di board."""
        for obj in board.game_objects:
            if obj.type == "DiamondButtonGameObject":
                return obj
        return None

    def next_move(self, bot: GameObject, board: Board) -> Tuple[int, int]:
        props = bot.properties
        pos = bot.position
        base = props.base
        time_left = getattr(board, "time_left", 999) # Waktu tersisa dalam game
        current_diamonds = props.diamonds
        MAX_DIAMOND_CAPACITY = getattr(props, "diamonds_carried_max", 5)

        current_turn_goal_pos: Optional[Position] = None # Tujuan untuk giliran ini

        # --- STRATEGI PRIORITAS TINGGI (Bisa langsung return/mengakhiri evaluasi) ---

        # 1. Greedy by Escape: Jika membawa diamond cukup banyak (>=3) dan musuh sangat dekat (<=2),
        #    lari ke base menggunakan rute tercepat (termasuk teleporter).
        if current_diamonds >= 3:
            for enemy_bot in board.bots:
                if enemy_bot.id != bot.id and self.distance(pos, enemy_bot.position) <= 2:
                    self.goal = self.get_best_teleport_or_target(pos, base, board)
                    # print(f"BOT V3 DEBUG: Escaping! To base. Diamonds: {current_diamonds}, Enemy at: {enemy_bot.position}")
                    return get_direction(pos.x, pos.y, self.goal.x, self.goal.y)

        # 2. Greedy by Return (Waktu Kritis DAN ADA PROFIT):
        #    Jika waktu hampir habis DAN bot membawa diamond, kembali ke base untuk skor.
        safe_time_buffer_steps_profit = 4  # Buffer langkah aman untuk kembali ke base
        effective_steps_to_base = self.distance_with_teleporter(pos, base, board)
        
        if current_diamonds > 0 and (time_left <= effective_steps_to_base + safe_time_buffer_steps_profit):
            self.goal = self.get_best_teleport_or_target(pos, base, board)
            # print(f"BOT V3 DEBUG: Time critical & profitable return. Diamonds: {current_diamonds}, Time Left: {time_left}, Steps to Base: {effective_steps_to_base}")
            return get_direction(pos.x, pos.y, self.goal.x, self.goal.y)

        # 3. V3 Feature: "Last Dash Diamond Grab"
        #    Jika waktu sangat kritis, tidak bawa diamond, tapi ada peluang ambil 1 diamond + pulang.
        last_dash_max_time_evaluation = 10 # Waktu maksimal tersisa untuk mengevaluasi aksi ini
        min_buffer_after_last_dash = 1    # Harus ada sisa waktu minimal setelah sampai base
        max_direct_dist_to_dash_diamond = 2 # Diamond harus sangat dekat secara langsung

        if current_diamonds == 0 and (time_left <= last_dash_max_time_evaluation):
            best_last_dash_diamond_obj: Optional[GameObject] = None
            min_total_steps_for_last_dash = float('inf')

            potential_diamonds_for_dash = [
                d for d in board.diamonds if self.distance(pos, d.position) <= max_direct_dist_to_dash_diamond
            ]
            
            for d_obj in potential_diamonds_for_dash:
                diamond_points = d_obj.properties.points
                # Cek apakah diamond muat (sebenarnya current_diamonds == 0, jadi selalu muat jika kapasitas > 0)
                if (diamond_points == 1 and 1 <= MAX_DIAMOND_CAPACITY) or \
                   (diamond_points == 2 and 2 <= MAX_DIAMOND_CAPACITY):
                    
                    dist_to_diamond_direct = self.distance(pos, d_obj.position)
                    # Setelah ambil diamond, kita akan berada di d_obj.position
                    steps_from_diamond_to_base = self.distance_with_teleporter(d_obj.position, base, board)
                    
                    # Perkirakan 1 langkah untuk mengambil diamond (bergerak ke petaknya)
                    total_steps_this_dash = dist_to_diamond_direct + steps_from_diamond_to_base 
                    
                    if total_steps_this_dash < min_total_steps_for_last_dash and \
                       (total_steps_this_dash + min_buffer_after_last_dash <= time_left):
                        min_total_steps_for_last_dash = total_steps_this_dash
                        best_last_dash_diamond_obj = d_obj
            
            if best_last_dash_diamond_obj:
                current_turn_goal_pos = best_last_dash_diamond_obj.position
                # print(f"BOT V3 DEBUG: Last Dash Diamond Grab! Target: {current_turn_goal_pos}, Time Left: {time_left}, Est. steps: {min_total_steps_for_last_dash}")
                # Tidak langsung return, biarkan diproses di akhir jika ini adalah goal terbaik


        # --- PENETAPAN TUJUAN STRATEGIS (Jika tidak ada override darurat dari atas DAN belum ada goal dari Last Dash) ---

        # 4. Greedy by Tackle (Langsung):
        #    Jika musuh dengan >= 2 diamond berada di petak sebelah (jarak 1).
        if not current_turn_goal_pos:
            for enemy_bot in board.bots:
                if enemy_bot.id != bot.id and \
                   self.distance(pos, enemy_bot.position) == 1 and \
                   getattr(enemy_bot.properties, "diamonds", 0) >= 2:
                    # Tackle jika bot miskin (kurang dari 2 diamond) ATAU musuh sangat kaya
                    if current_diamonds < 2 or getattr(enemy_bot.properties, "diamonds", 0) >= (MAX_DIAMOND_CAPACITY -1) :
                        current_turn_goal_pos = enemy_bot.position 
                        # print(f"BOT V3 DEBUG: Immediate Tackle! Target: {enemy_bot.position}")
                        break 
        
        # 5. Greedy by Inventory Full: Jika inventory penuh, kembali ke base.
        if not current_turn_goal_pos:
            if current_diamonds >= MAX_DIAMOND_CAPACITY:
                current_turn_goal_pos = self.get_best_teleport_or_target(pos, base, board)
                # print(f"BOT V3 DEBUG: Inventory Full. Going to base. Diamonds: {current_diamonds}")

        # 6. Greedy by Red Button:
        if not current_turn_goal_pos:
            red_button_obj = self.get_red_button(board)
            if red_button_obj:
                press_button = False
                diamonds_on_board_count = len(board.diamonds)
                
                if diamonds_on_board_count == 0 and current_diamonds < MAX_DIAMOND_CAPACITY:
                     press_button = True
                elif diamonds_on_board_count < 4 and current_diamonds < MAX_DIAMOND_CAPACITY -1 :
                    press_button = True
                elif diamonds_on_board_count < 8 and current_diamonds < (MAX_DIAMOND_CAPACITY // 2):
                    # Cek diamond terdekat (semua jenis, menggunakan jarak efektif)
                    closest_any_diamond = self.get_closest_diamond(bot, board) 
                    if closest_any_diamond:
                        dist_eff_to_button = self.distance_with_teleporter(pos, red_button_obj.position, board)
                        dist_eff_to_diamond = self.distance_with_teleporter(pos, closest_any_diamond.position, board)
                        if dist_eff_to_button < dist_eff_to_diamond - 2 or dist_eff_to_diamond > 7:
                            press_button = True
                    else: 
                        press_button = True
                
                if press_button:
                    current_turn_goal_pos = red_button_obj.position
                    # print(f"BOT V3 DEBUG: Pressing Red Button. Target: {red_button_obj.position}")
        
        # 7. Greedy by Tackle (Proaktif/Mendekat):
        #    Jika tidak membawa terlalu banyak diamond, dan ada musuh yang rentan (>=2 diamond) pada jarak 2.
        if not current_turn_goal_pos:
            if current_diamonds < MAX_DIAMOND_CAPACITY - (MAX_DIAMOND_CAPACITY // 2) + 1 : 
                for enemy_bot in board.bots:
                    if enemy_bot.id != bot.id and \
                       self.distance(pos, enemy_bot.position) == 2 and \
                       getattr(enemy_bot.properties, "diamonds", 0) >= 2:
                        current_turn_goal_pos = enemy_bot.position
                        # print(f"BOT V3 DEBUG: Proactive Tackle Approach. Target: {enemy_bot.position}")
                        break
        
        # 8. Greedy by Diamond Collection (menggunakan get_closest_diamond yang baru):
        if not current_turn_goal_pos:
            # get_closest_diamond sudah memperhitungkan teleporter dan kapasitas
            red_diamond_obj = self.get_closest_diamond(bot, board, red_only=True)
            blue_diamond_obj = self.get_closest_diamond(bot, board, blue_only=True)

            target_diamond_pos: Optional[Position] = None

            if red_diamond_obj and blue_diamond_obj:
                dist_eff_red = self.distance_with_teleporter(pos, red_diamond_obj.position, board)
                dist_eff_blue = self.distance_with_teleporter(pos, blue_diamond_obj.position, board)
                # Prioritaskan merah jika tidak terlalu jauh lebih dari biru (misal, selisih jarak <= 2)
                # atau jika merah secara signifikan lebih berharga (2 vs 1).
                if dist_eff_red <= dist_eff_blue + 2: 
                    target_diamond_pos = red_diamond_obj.position
                else:
                    target_diamond_pos = blue_diamond_obj.position
            elif red_diamond_obj:
                target_diamond_pos = red_diamond_obj.position
            elif blue_diamond_obj:
                target_diamond_pos = blue_diamond_obj.position
            
            if target_diamond_pos:
                current_turn_goal_pos = target_diamond_pos
                # print(f"BOT V3 DEBUG: Collecting Diamond. Target: {target_diamond_pos}")
            else: # Tidak ada diamond yang bisa diambil atau ditemukan
                if not current_turn_goal_pos: 
                     current_turn_goal_pos = self.get_best_teleport_or_target(pos, base, board)
                     # print(f"BOT V3 DEBUG: No diamonds to collect, defaulting to base. Target: {current_turn_goal_pos}")


        # 9. Aksi Default: Jika tidak ada tujuan spesifik dari strategi di atas, bergerak menuju base.
        if not current_turn_goal_pos:
            current_turn_goal_pos = self.get_best_teleport_or_target(pos, base, board)
            # print(f"BOT V3 DEBUG: Default action, going to base. Target: {current_turn_goal_pos}")

        # --- PENYESUAIAN AKHIR & EKSEKUSI ---
        self.goal = current_turn_goal_pos # Tetapkan goal yang dipilih untuk giliran ini

        # 10. Kembali ke Base Opportunistik: Jika bot berada di sebelah base-nya dan membawa diamond,
        #     prioritaskan untuk menaruh diamond tersebut, override goal sebelumnya jika perlu.
        if self.goal != base and self.distance(pos, base) == 1 and current_diamonds > 0:
            self.goal = base
            # print(f"BOT V3 DEBUG: Opportunistic return to base. Diamonds: {current_diamonds}")

        # Failsafe: Pastikan goal selalu ada
        if not self.goal:
            self.goal = base 
            # print(f"BOT V3 DEBUG: Failsafe, goal was None, setting to base.")
            
        # print(f"BOT V3 FINAL GOAL: {self.goal} for bot at {pos} with {current_diamonds} diamonds. Time: {time_left}")
        delta_x, delta_y = get_direction(pos.x, pos.y, self.goal.x, self.goal.y)
        return delta_x, delta_y

