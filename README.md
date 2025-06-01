# README - Bot Gachoan (Tubes 1)

## i. Penjelasan Singkat Algoritma Greedy yang Diimplementasikan

Bot Gachoan (`gachoan.py`) menerapkan serangkaian strategi greedy yang dievaluasi secara berurutan pada setiap langkah (`next_move`) untuk menentukan aksi terbaik. Prioritas utama diberikan pada situasi darurat atau kondisi yang paling menguntungkan secara langsung. Algoritma ini memanfaatkan perhitungan jarak Manhattan dan memperhitungkan penggunaan teleporter untuk optimasi jalur.

Berikut adalah poin-poin utama dari strategi greedy yang diimplementasikan:

1.  **Prioritas Darurat & Kondisi Kritis:**
    * **Lari ke Base (Greedy by Escape):** Jika bot membawa 3 diamond atau lebih dan ada musuh dalam jarak sangat dekat (≤2 petak), bot akan segera bergerak menuju base menggunakan rute tercepat (mempertimbangkan teleporter).
    * **Kembali ke Base karena Waktu (Greedy by Return - Waktu Kritis):** Jika waktu tersisa hampir habis (dengan memperhitungkan langkah efektif ke base + buffer aman) dan bot membawa diamond, bot akan kembali ke base.
    * **Ambil Diamond Terakhir & Pulang (Last Dash Diamond Grab):** Jika waktu sangat kritis, bot tidak membawa diamond, tetapi ada diamond sangat dekat (≤2 petak langsung) yang bisa diambil dan bot masih sempat kembali ke base sesudahnya, bot akan mencoba mengambil diamond tersebut.

2.  **Strategi Ofensif & Manajemen Inventaris:**
    * **Tackle Musuh Terdekat (Greedy by Tackle - Langsung):** Jika ada musuh dengan 2 diamond atau lebih pada jarak 1 petak, dan bot sendiri memiliki sedikit diamond (<2) atau musuh sangat kaya, bot akan mencoba men-tackle.
    * **Kembali ke Base karena Inventaris Penuh (Greedy by Inventory Full):** Jika inventaris diamond bot penuh, bot akan kembali ke base.
    * **Menekan Tombol Merah (Greedy by Red Button):** Bot akan menekan tombol merah jika:
        * Tidak ada diamond di papan dan bot belum penuh.
        * Jumlah diamond di papan sedikit (<4) dan bot masih bisa menampung lebih banyak.
        * Jumlah diamond di papan sedang (<8), bot memiliki ruang, dan jarak ke tombol lebih dekat/efisien daripada ke diamond terdekat, atau diamond terdekat terlalu jauh.
        * Tidak ada diamond sama sekali yang bisa diambil.
    * **Mendekati Musuh untuk Tackle (Greedy by Tackle - Proaktif):** Jika bot tidak membawa terlalu banyak diamond dan ada musuh dengan 2 diamond atau lebih pada jarak 2 petak, bot akan bergerak mendekati musuh tersebut.

3.  **Pengumpulan Diamond (Greedy by Diamond Collection):**
    * Bot akan mencari diamond terdekat yang bisa diambil, dengan memperhitungkan kapasitas inventaris dan penggunaan teleporter untuk menghitung jarak efektif.
    * Jika ada diamond merah dan biru, bot cenderung memprioritaskan diamond merah jika jaraknya tidak terlalu jauh berbeda dibandingkan diamond biru.

4.  **Aksi Default & Opportunistik:**
    * **Kembali ke Base (Default):** Jika tidak ada strategi di atas yang terpenuhi, bot akan bergerak menuju base-nya.
    * **Kembali ke Base Opportunistik:** Jika bot berada persis di sebelah base-nya dan membawa diamond, bot akan memprioritaskan untuk masuk ke base, bahkan jika ada target lain sebelumnya.

Fungsi pembantu seperti `distance_with_teleporter` digunakan untuk menghitung jarak terpendek dengan mempertimbangkan penggunaan satu pasang teleporter, dan `get_closest_diamond` mencari diamond terdekat dengan kriteria spesifik (merah/biru) dan kapasitas, juga menggunakan jarak efektif via teleporter. Fungsi `get_best_teleport_or_target` membantu menentukan apakah lebih cepat menuju target langsung atau melalui teleporter, dan mengembalikan langkah perantara (teleporter masuk) jika jalur teleporter lebih optimal.

## ii. Requirement Program dan Instalasi Tertentu Bila Ada

* **Bahasa Pemrograman:** Python 3.x
* **Library Standar Python:**
    * `typing` (Optional, List, Tuple)
    * `random` (Meskipun diimpor di `gachoan.py`, tidak secara eksplisit digunakan dalam logika yang terlihat. Mungkin untuk pengembangan di masa depan atau bagian dari template dasar.)
* **Dependensi Eksternal (Asumsi dari Struktur Proyek):**
    * Program ini dirancang untuk dijalankan dalam sebuah lingkungan game atau simulator yang menyediakan modul-modul berikut:
        * `game.logic.base` (berisi `BaseLogic`)
        * `game.models` (berisi `GameObject`, `Board`, `Position`)
        * `util` (berisi `get_direction`, diimpor sebagai `from ..util import get_direction` yang mengindikasikan struktur proyek tertentu di mana `util.py` berada satu level di atas direktori bot).
* **Instalasi:**
    * Pastikan Python 3.x terinstal.
    * Tidak ada langkah instalasi khusus untuk bot ini selain menempatkannya dalam struktur direktori yang benar sesuai dengan kebutuhan game engine/simulator yang digunakan. Bot ini (`gachoan.py`) harus ditempatkan di dalam folder `src/`.

## iii. Command atau Langkah-langkah dalam Meng-compile atau Build Program

* Program ini adalah skrip Python (`.py`) dan tidak memerlukan proses kompilasi atau build khusus.
* Untuk menjalankan bot, game engine atau simulator yang digunakan biasanya akan mengimpor dan menjalankan kelas `GachoanBot` dari file `src/gachoan.py` sesuai dengan mekanisme internalnya. Pastikan file `gachoan.py` berada di dalam folder `src` dalam struktur proyek yang diunggah.

## iv. Author (Identitas Pembuat)

* **Nama Kelompok:** GaChoAn
* **Anggota Kelompok:**
    * Garis Rayya Rabbani 123140018
    * Choirunnisa Syawaldina 123140136
    * Anisah Octa Rohila 123140137
