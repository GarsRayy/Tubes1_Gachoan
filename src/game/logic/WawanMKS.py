from typing import Optional, List
import random
from game.logic.base import BaseLogic
from game.models import GameObject, Board, Position
from ..util import get_direction # Pastikan path import ..util sudah benar

class WawanMKS(BaseLogic):
    def __init__(self):
        self.goal: Optional[Position] = None
        # Anda bisa menambahkan variabel untuk persistensi goal jika diperlukan
        # self.goal_persistence_counter = 0
        # self.MAX_GOAL_PERSISTENCE = 2 

    def distance(self, A: Position, B: Position) -> int:
        """Menghitung jarak Manhattan antara dua posisi."""
        return abs(A.x - B.x) + abs(A.y - B.y)

    def get_teleporters(self, board: Board) -> List[GameObject]:
        """Mendapatkan semua objek teleporter di board."""
        return [obj for obj in board.game_objects if obj.type == "TeleportGameObject"]

    def distance_with_teleporter(self, start: Position, end: Position, board: Board) -> int:
        """
        Menghitung jarak terpendek antara start dan end, mempertimbangkan penggunaan teleporter.
        Akan mencoba semua kombinasi pasangan teleporter masuk dan keluar.
        """
        teleporters = self.get_teleporters(board)
        direct_dist = self.distance(start, end)

        if len(teleporters) < 2: # Membutuhkan setidaknya satu pasang (masuk & keluar) untuk teleportasi yang berarti
            return direct_dist

        min_overall_dist = direct_dist
        
        for tp_entry in teleporters:
            for tp_exit in teleporters:
                if tp_entry.id == tp_exit.id: # Tidak bisa masuk dan keluar dari teleporter yang sama dalam satu aksi teleport
                    continue
                
                # Biaya: jarak ke teleporter masuk + jarak dari teleporter keluar ke tujuan.
                # Asumsi aksi teleport itu sendiri memiliki biaya minimal (misalnya 1 langkah) atau 0,
                # yang secara implisit ditangani dengan bergerak ke petak teleporter masuk.
                dist_via_tp = self.distance(start, tp_entry.position) + self.distance(tp_exit.position, end)
                min_overall_dist = min(min_overall_dist, dist_via_tp)
        
        return min_overall_dist

    def get_best_teleport_or_base(self, bot_pos: Position, base_pos: Position, board: Board) -> Position:
        """
        Menentukan posisi target langkah berikutnya untuk mencapai base_pos,
        mempertimbangkan perjalanan langsung atau menggunakan pasangan teleporter.
        Mengembalikan base_pos itu sendiri, atau posisi teleporter masuk yang optimal.
        """
        teleporters = self.get_teleporters(board)
        
        # Jalur 1: Langsung ke base
        dist_direct = self.distance(bot_pos, base_pos)
        
        best_path_dist = dist_direct
        next_step_target = base_pos # Awalnya, asumsikan jalur langsung adalah yang terbaik

        if len(teleporters) >= 2: # Teleportasi yang berarti memerlukan setidaknya satu teleporter masuk dan satu keluar
            for tp_entry in teleporters:
                for tp_exit in teleporters:
                    if tp_entry.id == tp_exit.id:
                        continue
                    
                    # Jarak: ke tp_entry + dari tp_exit ke base
                    dist_via_this_tp_pair = self.distance(bot_pos, tp_entry.position) + \
                                            self.distance(tp_exit.position, base_pos)
                    
                    if dist_via_this_tp_pair < best_path_dist:
                        best_path_dist = dist_via_this_tp_pair
                        next_step_target = tp_entry.position # Tujuan langsung adalah mencapai teleporter masuk ini
        
        return next_step_target

    def get_closest_diamond(self, bot: GameObject, board: Board, red_only=False, blue_only=False) -> Optional[GameObject]:
        """
        Mencari diamond terdekat yang bisa diambil bot sesuai dengan kapasitas dan filter warna.
        """
        diamonds_found = []
        MAX_DIAMOND_CAPACITY = getattr(bot.properties, "diamonds_carried_max", 5) # Gunakan properti bot jika ada, fallback ke 5
        current_diamonds_held = bot.properties.diamonds

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

        closest_diamond_obj = diamonds_found[0]
        min_dist_to_diamond = self.distance(bot.position, closest_diamond_obj.position)

        for d_obj in diamonds_found[1:]:
            dist = self.distance(bot.position, d_obj.position)
            if dist < min_dist_to_diamond:
                closest_diamond_obj = d_obj
                min_dist_to_diamond = dist
        return closest_diamond_obj

    def find_enemy_to_tackle(self, bot: GameObject, board: Board) -> Optional[Position]:
        """Mencari musuh pada jarak 2 yang membawa >= 2 diamond untuk didekati."""
        for enemy in board.bots:
            if enemy.id != bot.id and self.distance(bot.position, enemy.position) == 2:
                if getattr(enemy.properties, "diamonds", 0) >= 2: # Musuh membawa setidaknya 2 diamond
                    return enemy.position # Target adalah posisi musuh saat ini untuk bergerak ke arahnya
        return None

    def get_red_button(self, board: Board) -> Optional[GameObject]:
        """Mendapatkan objek Tombol Merah (Diamond Button) di board."""
        for obj in board.game_objects:
            if obj.type == "DiamondButtonGameObject":
                return obj
        return None

    def next_move(self, bot: GameObject, board: Board) -> tuple[int, int]:
        props = bot.properties
        pos = bot.position
        base = props.base
        time_left = getattr(board, "time_left", 999) # Waktu tersisa dalam game
        current_diamonds = props.diamonds
        MAX_DIAMOND_CAPACITY = getattr(props, "diamonds_carried_max", 5)

        current_turn_goal_pos: Optional[Position] = None

        # --- STRATEGI PRIORITAS TINGGI (Bisa langsung return) ---

        # 1. Greedy by Escape: Jika membawa diamond cukup banyak (>=3) dan musuh sangat dekat (<=2),
        #    lari ke base menggunakan rute tercepat (termasuk teleporter).
        if current_diamonds >= 3:
            for enemy_bot in board.bots:
                if enemy_bot.id != bot.id and self.distance(pos, enemy_bot.position) <= 2:
                    self.goal = self.get_best_teleport_or_base(pos, base, board)
                    return get_direction(pos.x, pos.y, self.goal.x, self.goal.y)

        # 2. Greedy by Return (Waktu Kritis): Jika waktu hampir habis, kembali ke base.
        #    Buffer waktu memastikan bot tidak terjebak.
        safe_time_buffer_steps = 4 # Buffer langkah aman untuk kembali ke base
        effective_steps_to_base = self.distance_with_teleporter(pos, base, board) # Jarak minimum ke base (bisa via TP)
        
        if current_diamonds > 0 and (time_left <= effective_steps_to_base + safe_time_buffer_steps):
            # Bot membawa diamond dan waktu mepet, jadi pulang adalah prioritas untuk skor.
            self.goal = self.get_best_teleport_or_base(pos, base, board)
            # print(f"BOT DEBUG: Time critical & profitable return. Diamonds: {current_diamonds}, Time Left: {time_left}, Steps to Base: {effective_steps_to_base}")
            return get_direction(pos.x, pos.y, self.goal.x, self.goal.y)

        # --- PENETAPAN TUJUAN STRATEGIS (Jika tidak ada override darurat) ---

        # 3. Greedy by Tackle (Langsung):
        #    Jika musuh dengan >= 2 diamond berada di petak sebelah (jarak 1).
        #    Lakukan tackle jika bot membawa sedikit diamond ATAU musuh kaya, agar risiko sepadan.
        if not current_turn_goal_pos:
            for enemy_bot in board.bots:
                if enemy_bot.id != bot.id and \
                   self.distance(pos, enemy_bot.position) == 1 and \
                   getattr(enemy_bot.properties, "diamonds", 0) >= 2:
                    # Tackle jika bot miskin (kurang dari 2 diamond) ATAU musuh sangat kaya
                    if current_diamonds < 2 or getattr(enemy_bot.properties, "diamonds", 0) >= (MAX_DIAMOND_CAPACITY -1) :
                        current_turn_goal_pos = enemy_bot.position # Bergerak ke petak musuh untuk tackle
                        break
        
        # 4. Greedy by Inventory Full: Jika inventory penuh, kembali ke base.
        if not current_turn_goal_pos:
            if current_diamonds >= MAX_DIAMOND_CAPACITY:
                current_turn_goal_pos = self.get_best_teleport_or_base(pos, base, board)

        # 5. Greedy by Red Button:
        #    Pertimbangkan menekan tombol jika diamond langka atau tombol adalah opsi yang jauh lebih baik.
        if not current_turn_goal_pos:
            red_button_obj = self.get_red_button(board)
            if red_button_obj:
                press_button = False
                diamonds_on_board_count = len(board.diamonds)
                # Kondisi untuk menekan tombol:
                if diamonds_on_board_count == 0 and current_diamonds < MAX_DIAMOND_CAPACITY: # Tidak ada diamond, bot tidak penuh
                     press_button = True
                elif diamonds_on_board_count < 4 and current_diamonds < MAX_DIAMOND_CAPACITY -1 : # Diamond sedikit, bot punya ruang
                    press_button = True
                elif diamonds_on_board_count < 8 and current_diamonds < (MAX_DIAMOND_CAPACITY // 2): # Diamond sedang, bot masih kosong
                    closest_any_diamond = self.get_closest_diamond(bot, board) # Cek diamond terdekat (semua jenis)
                    if closest_any_diamond:
                        # Tekan jika tombol jauh lebih dekat daripada diamond atau diamond jauh
                        if self.distance(pos, red_button_obj.position) < self.distance(pos, closest_any_diamond.position) - 2 or \
                           self.distance(pos, closest_any_diamond.position) > 7:
                            press_button = True
                    else: # Tidak ada diamond yang bisa diambil, tombol jadi pilihan
                        press_button = True
                
                if press_button:
                    current_turn_goal_pos = red_button_obj.position
        
        # 6. Greedy by Tackle (Proaktif):
        #    Jika tidak membawa terlalu banyak diamond, dan ada musuh yang rentan (>=2 diamond) pada jarak 2.
        if not current_turn_goal_pos:
            # Jangan terlalu agresif jika membawa banyak diamond (misalnya, kurang dari separuh kapasitas)
            if current_diamonds < MAX_DIAMOND_CAPACITY - (MAX_DIAMOND_CAPACITY // 2) +1 : 
                proactive_tackle_target_pos = self.find_enemy_to_tackle(bot, board) # Sudah cek diamond musuh >= 2
                if proactive_tackle_target_pos:
                    current_turn_goal_pos = proactive_tackle_target_pos # Bergerak menuju musuh
        
        # 7. Greedy by Diamond Collection:
        if not current_turn_goal_pos:
            red_diamond_obj = self.get_closest_diamond(bot, board, red_only=True) # Cek kapasitas untuk merah
            blue_diamond_obj = self.get_closest_diamond(bot, board, blue_only=True) # Cek kapasitas untuk biru

            # Skenario A: Bot hampir penuh (misalnya, butuh 1-2 poin untuk maks)
            if current_diamonds >= MAX_DIAMOND_CAPACITY - 2: # Jika kapasitas 5, berarti punya 3 atau 4 diamond
                # Prioritaskan merah jika muat dan cukup dekat (misal, jarak <= 5)
                if red_diamond_obj and self.distance(pos, red_diamond_obj.position) <= 5: # Kapasitas sudah dicek di get_closest_diamond
                    current_turn_goal_pos = red_diamond_obj.position
                # Atau, jika biru muat (berarti bot punya 4, butuh 1) dan dekat
                elif blue_diamond_obj and self.distance(pos, blue_diamond_obj.position) <= 4:
                    current_turn_goal_pos = blue_diamond_obj.position
                # Jika tidak bisa top-up dengan diamond terdekat, kembali ke base
                else:
                    current_turn_goal_pos = self.get_best_teleport_or_base(pos, base, board)
            
            # Skenario B: Bot punya lebih banyak kapasitas
            else:
                can_take_red = red_diamond_obj is not None
                can_take_blue = blue_diamond_obj is not None

                if can_take_red and can_take_blue:
                    dist_red = self.distance(pos, red_diamond_obj.position)
                    dist_blue = self.distance(pos, blue_diamond_obj.position)
                    # Prioritaskan merah jika tidak terlalu jauh lebih dari biru (misal, selisih jarak <= 2)
                    # atau jika merah secara signifikan lebih berharga (2 vs 1).
                    if dist_red <= dist_blue + 2: 
                        current_turn_goal_pos = red_diamond_obj.position
                    else:
                        current_turn_goal_pos = blue_diamond_obj.position
                elif can_take_red:
                    current_turn_goal_pos = red_diamond_obj.position
                elif can_take_blue:
                    current_turn_goal_pos = blue_diamond_obj.position
                # Jika tidak ada diamond yang bisa diambil (kosong atau tidak muat)
                else:
                    current_turn_goal_pos = self.get_best_teleport_or_base(pos, base, board)

        # 8. Aksi Default: Jika tidak ada tujuan spesifik dari strategi di atas, bergerak menuju base.
        if not current_turn_goal_pos:
            current_turn_goal_pos = self.get_best_teleport_or_base(pos, base, board)

        # --- PENYESUAIAN AKHIR ---
        self.goal = current_turn_goal_pos # Tetapkan goal yang dipilih untuk giliran ini

        # 9. Kembali ke Base Opportunistik: Jika bot berada di sebelah base-nya dan membawa diamond,
        #    prioritaskan untuk menaruh diamond tersebut.
        if self.goal != base and self.distance(pos, base) == 1 and current_diamonds > 0:
            self.goal = base

        # Failsafe: Pastikan goal selalu ada (seharusnya sudah dicakup oleh aksi default)
        if not self.goal:
            self.goal = base # Jika karena suatu hal goal belum ter-set, default ke base.
            
        delta_x, delta_y = get_direction(pos.x, pos.y, self.goal.x, self.goal.y)
        return delta_x, delta_y