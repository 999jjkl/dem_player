 dem_player 使用說明
 版本：0.19.9
 主程式：music_player.py
============================================================
一、快速開始
------------------------------------------------------------
1. 安裝 Python 依賴：
   pip install PyQt6 python-vlc numpy sounddevice mutagen

   必要：
   - PyQt6
   - python-vlc

   選用：
   - numpy        ：系統音訊頻譜用
   - sounddevice  ：系統音訊擷取用
   - mutagen      ：讀取 ID3 / 專輯 / 演出者等標籤

2. 準備外部檔案，放在 music_player.py 同一目錄：
   - VLC：libvlc.dll、libvlccore.dll、plugins/ 目錄
   - BASS：bass.dll、bassmidi.dll、soundfont.sf2
   - 轉換引擎：
     - ffmpeg.exe        ：部分模組格式
     - asapconv.exe      ：ASAP / Atari 格式
     - zxtune-cli.exe    ：SID / VGM
     - zxtune123.exe     ：SID / VGM 備用
     - furnace.exe       ：.dnm / .ftm
   - 可選資源：
     - font.ttf          ：自訂字型
     - FPT.ico           ：視窗 / 系統匣圖示
     - background.png    ：背景圖模式用
     - soundfont.sf2     ：MIDI 音源

3. 執行：
   python music_player.py

4. 首次啟動會自動遷移舊資料：
   - 舊版 data.json、data.txt、list.txt、love.txt、Cache.json
     會轉成新版資料檔。
   - 舊檔通常會改名為 *_old2.*。
   - 新版資料檔：
     settings.dpst
     play_list.dppls
     play_history_counts.dpphc
     cache.dpch

5. 進入程式後：
   - 用 F7 進設定頁。
   - 選 Add Music Folder... 加入音樂資料夾。
   - 用方向鍵選曲，Enter 播放。
   - 主要操作以鍵盤為主。

============================================================
二、目錄與檔案放置
============================================================
建議目錄結構：

你的資料夾/
├─ music_player.py
├─ font.ttf
├─ FPT.ico
├─ background.png
├─ libvlc.dll
├─ libvlccore.dll
├─ plugins/
│  └─ ... VLC plugins ...
├─ bass.dll
├─ bassmidi.dll
├─ soundfont.sf2
├─ ffmpeg.exe
├─ asapconv.exe
├─ zxtune-cli.exe
├─ furnace.exe
└─ data/
   └─ player_data_*.log

資料檔會寫在「程式所在目錄」：
- 直接跑 .py：music_player.py 所在目錄。
- 打包成 .exe：.exe 所在目錄。
- 日誌：data/player_data_%H.%M.%S-%d.%m.%Y.log。

============================================================
三、介面操作
============================================================
左側面板：
- FILE BROWSER：檔案瀏覽。
- SETTING：設定頁。
- F4：顯示 / 隱藏左側面板。
- F7：切換檔案頁 / 設定頁。

右側面板：
- Track：目前曲名，過長會跑馬燈。
- Artist / Album / Track#：音樂標籤。
- 進度條：顯示目前進度與時間。
- Loop：循環模式。
- Volume：音量。
- Audio Level：文字頻譜。
- 快捷鍵提示。
- 封面圖：若資料夾有 cover.jpg、folder.jpg 等會顯示。

視窗操作：
- 視窗為無邊框。
- 在視窗最上方約 40px 區域按住左鍵可拖曳。
- 拖曳時會顯示外框，放開後才實際移動。
- 右上角：
  - ：最小化。
  - X：關閉程式。
- 系統匣圖示：
  - 右鍵選單：stop、Previous song、Next song、quit。
  - 點左鍵目前沒有動作。

注意：
程式把 file_list、settings_list、search_input、progress_text、
volume_text 與多數 QLabel 設為滑鼠穿透。
因此列表與設定頁主要用鍵盤操作，不是用滑鼠點。
滑鼠主要用來拖曳標題列與點右上角按鈕。

============================================================
四、快捷鍵總表
============================================================
按鍵           功能
------------------------------------------------------------
↑ / ↓          清單上下移動
Enter          開啟資料夾 / 播放選取項目 / 開啟 CUE / M3U
Backspace      返回上一層；搜尋框有焦點時為刪除字元
F1             播放 / 暫停切換
F2             音量 -1
F3             音量 +1
F4             顯示 / 隱藏左側面板
F5             循環模式：OFF -> SINGLE -> LIST
F6             視窗模式：Normal -> Fullscreen -> Mini -> Bar
F7             設定頁開 / 關
F8             搜尋框聚焦；再按一次取消聚焦
F9             加入 / 移除我的最愛
Esc            重置播放器狀態
← / →          後退 / 前進 1 秒

搜尋框有焦點時：
- 一般字元會輸入到搜尋框。
- Enter 執行搜尋。
- Backspace 刪除字元。

============================================================
五、設定頁說明
============================================================
用 F7 進入設定頁，用 ↑ / ↓ 選擇，Enter 執行。

設定項目：
- Always on Top：視窗置頂 Y/N。
- Style：循環切換主題。
- Audio Level：是否顯示頻譜。
- Audio Level Source：file / system。
- Audio Level Mode：all / volume。
- Output Device：主輸出裝置，VLC + BASS 同步。
- Advanced Audio >>：展開進階音訊。
  - VLC Device：單獨選 VLC 裝置。
  - BASS Device：單獨選 BASS 裝置。
  - << Hide Advanced Audio：收起。
- Show Play Counts：Most Played 是否顯示播放次數。
- Background：transparent / solid / image。
- Log Save：是否寫入日誌。
- Show Duration：是否顯示 [AUD mm:ss]。
- Show Cover Art：是否顯示封面。
- Time Format：MM:SS.CC / MM:SS。
- Engine Mode：Normal / VLC / BASS。

--- Music Folders ---
- Remove Folder [i]：移除第 i 個來源資料夾。
- Add Music Folder...：加入音樂資料夾。
- Refresh File List：重新整理目前目錄。

--- Maintenance ---
- Clear History：清除歷史。
- Clear Play Counts：清除播放次數。
- Clear Favorites：清除我的最愛。
- Clear Duration Cache：清除時長快取。
- Reset All Settings：重置所有設定。

--- About ---
- About dem_player：關於本程式。

============================================================
六、播放引擎與格式支援
============================================================
Engine Mode：
- Normal：自動選擇。
- VLC：盡量使用 VLC。
- BASS：盡量使用 BASS，BASS 不可用時回退 VLC。

Normal 模式選擇邏輯：
- 若開啟 Audio Level，且格式支援，優先 BASS。
- .mod、.xm、.it、.s3m、.mtm、.umx、.mo3：BASS。
- .mid、.midi、.rmi、.kar：BASS MIDI，
  需要 bassmidi.dll + soundfont.sf2。
- .sid、.vgm、.vgz：ZXTune。
- .sap、.cmc、.cm3、.cmr、.cms、.dmc、.dlt、
  .mpt、.mpd、.rmt、.tmc、.tm8、.tm2、.fc：ASAP。
- .mt2、.stm、.ult、.669、.far：libopenmpt / ffmpeg。
- .dnm、.ftm：Furnace。
- 其他：VLC。

支援的副檔名：
.mp3 .wav .ogg .m4a .flac .dnm .ftm .it .mid .midi .mod
.mptm .mt2 .rmi .s3m .sap .sid .tm8 .xm .vgm .vgz .swf
.opus .alac .aac .wma

部分格式只有在對應引擎存在時才會出現在清單中。

============================================================
七、檔案瀏覽、M3U、CUE、收藏、歷史
============================================================
來源清單：
首頁會顯示：
- [FILE]：你加入的音樂資料夾。
- [LISTxxx] favorites：我的最愛清單。
- [HISTORY]：播放歷史。
- [MOST] Most Played：播放次數排行。

資料夾內：
- [DIR]：子資料夾。
- [CUE]：CUE 檔。
- [M3U]：M3U / M3U8 清單。
- [AUD] 或 [AUD mm:ss]：音訊檔。
- [..]：返回上一層。

M3U：
支援：
- 本地相對路徑。
- 絕對路徑。
- http:// / https:// 網路串流。

CUE：
支援解析：
- FILE
- TRACK
- TITLE
- PERFORMER
- INDEX 01

CUE 分段播放：
- VLC：使用 :start-time / :stop-time。
- BASS：用計時器檢查 end_ms。

我的最愛：
- 在一般清單按 F9：輸入編號 0~512，
  會存成三位數，例如 001。
- 在 FAVORITES: 頁面按 F9：移除目前選取項目。

歷史與播放次數：
- 播放成功會加入歷史，最多 100 筆，最新在最前。
- 播放次數會累加。
- Most Played 依播放次數排序。

============================================================
八、音訊輸出裝置
============================================================
主輸出裝置：
設定頁 -> Output Device：
- 列出 VLC 可用裝置。
- 選擇後會同步設定 VLC 與 BASS。
- System Default 表示預設裝置。

進階音訊：
設定頁 -> Advanced Audio >>：
- VLC Device：只改 VLC。
- BASS Device：只改 BASS。
- BASS 裝置以名稱匹配。

切換裝置時：
- 會停止目前播放。
- 重建 VLC player 與 BASS engine。
- 若原本正在播放，會嘗試在 500ms 後恢復播放。

============================================================
九、音訊頻譜 / Audio Level
============================================================
開啟 Audio Level 後，右側會顯示：
- Bass:
- Mid:
- Treble:
- Volume:

Source = file：
- BASS 播放：直接取 BASS level。
- VLC 播放：用 BASS 額外解碼流做 FFT，
  取得 Bass / Mid / Treble。
- 需要 BASS 可用。

Source = system：
- 用 sounddevice 擷取系統音訊。
- 會尋找 loopback、立體聲混音、Stereo Mix。
- 需要 numpy 與 sounddevice。
- 若找不到，會回退 file。

Mode：
- all：顯示 Bass / Mid / Treble / Volume。
- volume：只顯示 Volume。

注意：
若 Engine Mode = VLC，頻譜會歸零，
避免額外解碼負擔。

============================================================
十、資料檔與遷移
============================================================
新版資料檔：
- settings.dpst：設定。
- play_list.dppls：來源資料夾與我的最愛。
- play_history_counts.dpphc：歷史與播放次數。
- cache.dpch：資料夾時長掃描快取。

舊版支援：
- Cache.json、Cache_old2.json
- data.json、data_old2.json
- data.txt、data_old2.txt
- list.txt、list_old2.txt
- love.txt、love_old2.txt

首次啟動若新版不存在，會自動遷移。
若三個主要新版檔案都存在，則不遷移。

這些都是 JSON 格式，可在程式關閉後手動編輯。

============================================================
十一、日誌
============================================================
- 預設開啟。
- 路徑：data/player_data_%H.%M.%S-%d.%m.%Y.log
- 可在設定頁 Log Save 開 / 關。
- 日誌等級預設 INFO = 20。
- 可記錄：
  - 啟動 / 關閉。
  - 資料遷移。
  - VLC / BASS 初始化。
  - 播放檔案。
  - 錯誤與例外。

若程式閃退，先看 data/ 內最新日誌。

============================================================
十二、打包成 EXE
============================================================
可用 PyInstaller。Windows 範例：

pyinstaller --noconfirm --windowed --name dem_player ^
  --add-data "font.ttf;." ^
  --add-data "FPT.ico;." ^
  --add-data "background.png;." ^
  --add-data "soundfont.sf2;." ^
  --add-binary "bass.dll;." ^
  --add-binary "bassmidi.dll;." ^
  --add-binary "libvlc.dll;." ^
  --add-binary "libvlccore.dll;." ^
  --add-data "plugins;plugins" ^
  --add-binary "ffmpeg.exe;." ^
  --add-binary "asapconv.exe;." ^
  --add-binary "zxtune-cli.exe;." ^
  --add-binary "furnace.exe;." ^
  music_player.py

注意：
- Windows 的 --add-data 分隔符是 ;。
- VLC 通常需要整個 plugins/ 目錄，不只是 libvlc.dll。
- 打包後資源會在 _MEIPASS，程式用 resource_path() 找。
- 資料檔會寫在 .exe 所在目錄。
- 缺少某個選用檔案時，可省略對應 --add-*。

============================================================
十三、常見問題
============================================================
1. 程式閃退
   看 data/player_data_*.log。
   最常見是 VLC / BASS DLL 缺少或位數不符。

2. VLC 無法初始化
   確認：
   - libvlc.dll
   - libvlccore.dll
   - plugins/
   - 與 Python / EXE 位數一致，例如都是 64-bit。

3. BASS 不可用
   確認：
   - bass.dll
   - bassmidi.dll（MIDI 才需要）
   - soundfont.sf2

4. MIDI 沒聲音
   需要 bassmidi.dll + soundfont.sf2。
   若 BASS MIDI 不可用，會回退 VLC。

5. 頻譜不動
   確認：
   - Audio Level 已開啟。
   - 有安裝 numpy。
   - BASS 可用。
   - Engine Mode 不是 VLC。
   - Audio Level Source 若選 system，
     需 sounddevice 與 Stereo Mix / loopback。

6. 無法播放 .dnm / .ftm
   需要 furnace.exe。

7. 無法播放 SID / VGM
   需要 zxtune-cli.exe 或 zxtune123.exe。

8. 無法播放 ASAP 格式
   需要 asapconv.exe。

9. 無法播放 MT2 / STM / ULT / 669 / FAR
   需要 ffmpeg.exe。

10. 列表不能用滑鼠點
    這是設計。請用 ↑ / ↓ 與 Enter。
    滑鼠主要用於標題列拖曳與右上角按鈕。

11. 資料沒保存
    確認程式目錄有寫入權限。
    若放在 Program Files，可能需改放其他目錄或以管理員執行。

============================================================
十四、建議使用流程
============================================================
1. 安裝依賴。
2. 放好 VLC / BASS / 轉換引擎與資源。
3. 執行 python music_player.py。
4. F7 -> Add Music Folder... 加入音樂。
5. 用 ↑ / ↓ 選資料夾，Enter 進入。
6. 選曲，Enter 播放。
7. F1 暫停，F2 / F3 調音量，F5 改循環。
8. F8 搜尋，F9 收藏。
9. F6 切換視窗模式。
10. 設定頁可調音訊裝置、主題、背景、頻譜、引擎模式。
11. 關閉時會自動儲存設定、歷史、播放次數與快取。
