import streamlit as st
from yt_dlp import YoutubeDL
from pathlib import Path
from tempfile import TemporaryDirectory
import shutil
import re
from typing import Optional, Tuple

st.title("YouTube Video Downloader with Time Clipping")

def parse_time_to_seconds(time_str: str) -> Optional[int]:
    """時間文字列を秒数に変換する
    
    対応フォーマット:
    - HH:MM:SS (例: 1:30:45)
    - MM:SS (例: 5:30)
    - SS (例: 90)
    """
    if not time_str or not time_str.strip():
        return None
    
    time_str = time_str.strip()
    
    # 秒数のみ (数字のみ)
    if re.match(r'^\d+$', time_str):
        return int(time_str)
    
    # MM:SS フォーマット
    mm_ss_match = re.match(r'^(\d+):(\d+)$', time_str)
    if mm_ss_match:
        minutes, seconds = map(int, mm_ss_match.groups())
        return minutes * 60 + seconds
    
    # HH:MM:SS フォーマット
    hh_mm_ss_match = re.match(r'^(\d+):(\d+):(\d+)$', time_str)
    if hh_mm_ss_match:
        hours, minutes, seconds = map(int, hh_mm_ss_match.groups())
        return hours * 3600 + minutes * 60 + seconds
    
    return None

def validate_time_range(start_time: Optional[int], end_time: Optional[int]) -> Tuple[bool, str]:
    """時間範囲の妥当性をチェックする"""
    if start_time is not None and end_time is not None:
        if start_time >= end_time:
            return False, "開始時間は終了時間より前である必要があります"
    return True, ""

# ── モード選択タブ ───────────────────────────────────
tab1, tab2 = st.tabs(["🎯 個別指定ダウンロード", "📦 一括ダウンロード"])

with tab1:
    st.subheader("時間指定付き個別ダウンロード")
    st.write("URLを個別に入力し、必要に応じて切り出したい時間範囲を指定してください。時間が空欄の場合は動画全体をダウンロードします。")
    
    # セッション状態の初期化
    if 'video_entries' not in st.session_state:
        st.session_state.video_entries = [{'url': '', 'start_time': '', 'end_time': ''}]
    
    # 動画エントリーの管理
    for i, entry in enumerate(st.session_state.video_entries):
        col1, col2, col3, col4 = st.columns([3, 1, 1, 0.5])
        
        with col1:
            entry['url'] = st.text_input(
                f"YouTube URL {i+1}",
                value=entry['url'],
                placeholder="https://youtu.be/... または https://www.youtube.com/watch?v=...",
                key=f"url_{i}"
            )
        
        with col2:
            entry['start_time'] = st.text_input(
                "開始時間",
                value=entry['start_time'],
                placeholder="例: 1:30 または 90",
                key=f"start_{i}"
            )
        
        with col3:
            entry['end_time'] = st.text_input(
                "終了時間",
                value=entry['end_time'],
                placeholder="例: 3:45 または 225",
                key=f"end_{i}"
            )
        
        with col4:
            if st.button("削除", key=f"remove_{i}"):
                if len(st.session_state.video_entries) > 1:
                    st.session_state.video_entries.pop(i)
                    st.rerun()
    
    # 動画エントリーを追加するボタン
    if st.button("➕ 動画を追加"):
        st.session_state.video_entries.append({'url': '', 'start_time': '', 'end_time': ''})
        st.rerun()
    
    # 時間フォーマットの説明
    with st.expander("⏰ 時間指定フォーマット"):
        st.write("""
        以下のフォーマットがサポートされています：
        - **秒数のみ**: `90` (90秒)
        - **分:秒**: `1:30` (1分30秒)
        - **時:分:秒**: `1:30:45` (1時間30分45秒)
        
        空欄の場合は制限なしとなります。
        """)
        
        st.info("🤖 **bot検出回避時間指定**: User-Agent偵装、リトライ機能、待機時間設定などでYouTubeのbot検出を回避。")
    
    # 個別指定ダウンロードボタン
    individual_download = st.button("🎯 個別指定ダウンロード", type="primary")

with tab2:
    st.subheader("一括ダウンロード（時間指定なし）")
    st.write("複数のYouTube URLを1行につき1つずつ貼り付けて、一括でダウンロードできます。すべて動画全体がダウンロードされます。")
    
    # 一括ダウンロード用のテキストエリア
    bulk_urls = st.text_area(
        "YouTube URLs（1行につき1つ）",
        height=200,
        placeholder="https://youtu.be/...\nhttps://www.youtube.com/watch?v=...\nhttps://youtu.be/...",
        key="bulk_urls"
    )
    
    # 一括ダウンロードボタン
    bulk_download = st.button("📦 一括ダウンロード", type="primary")

# ── ダウンロード処理 ───────────────────────────────────
# 個別指定ダウンロードまたは一括ダウンロードのいずれかが実行される
run_dl = individual_download or bulk_download
download_mode = "individual" if individual_download else "bulk" if bulk_download else None

# ------------------------------------------------------------------
# ① Download ボタンが押されたときだけ動画を取得して session_state に保存
# ------------------------------------------------------------------
if run_dl:
    # 入力検証
    valid_entries = []
    
    if download_mode == "individual":
        # 個別指定モードの処理
        for i, entry in enumerate(st.session_state.video_entries):
            if entry['url'].strip():
                start_seconds = parse_time_to_seconds(entry['start_time'])
                end_seconds = parse_time_to_seconds(entry['end_time'])
                
                # 時間範囲の検証
                is_valid, error_msg = validate_time_range(start_seconds, end_seconds)
                if not is_valid:
                    st.error(f"動画 {i+1}: {error_msg}")
                    st.stop()
                
                valid_entries.append({
                    'url': entry['url'].strip(),
                    'start_time': start_seconds,
                    'end_time': end_seconds,
                    'start_str': entry['start_time'],
                    'end_str': entry['end_time']
                })
    
    elif download_mode == "bulk":
        # 一括ダウンロードモードの処理
        urls = [u.strip() for u in bulk_urls.splitlines() if u.strip()]
        for url in urls:
            valid_entries.append({
                'url': url,
                'start_time': None,
                'end_time': None,
                'start_str': '',
                'end_str': ''
            })
    
    if not valid_entries:
        st.warning("URL が入力されていません")
        st.stop()

    # 時間指定のチェックを先に実行
    time_specified = any(entry['start_time'] is not None or entry['end_time'] is not None for entry in valid_entries)
    
    # ffmpegのチェック
    if time_specified and shutil.which("ffmpeg") is None:
        st.warning(
            "⚠️ ffmpeg が見つかりません。時間指定機能が制限される可能性があります。"
        )
    
    # bot検出回避のための事前情報表示
    if time_specified:
        st.info("🤖 YouTubeのbot検出回避機能を有効化してダウンロードを開始します。")

    mode_text = "個別指定" if download_mode == "individual" else "一括"
    efficiency_note = "（bot検出回避リトライ付き）" if time_specified else ""
    
    with st.spinner(f"{len(valid_entries)} 本を{mode_text}ダウンロード中{efficiency_note}…"):
        with TemporaryDirectory() as td:
            out_dir = Path(td)
            
            st.session_state["files"] = []
            
            for entry in valid_entries:
                url = entry['url']
                start_time = entry['start_time']
                end_time = entry['end_time']
                start_str = entry['start_str']
                end_str = entry['end_str']
                
                try:
                    # 基本のyt-dlpオプション（bot検出回避設定付き）
                    ydl_opts = {
                        "format": (
                            "bestvideo[ext=mp4][height<=1080]+"
                            "bestaudio[ext=m4a]/best[ext=mp4][height<=1080]"
                        ),
                        "merge_output_format": "mp4",
                        "quiet": True,
                        # bot検出回避のための設定
                        "http_headers": {
                            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                            "Accept-Language": "en-US,en;q=0.5",
                            "Accept-Encoding": "gzip, deflate",
                            "DNT": "1",
                            "Connection": "keep-alive",
                            "Upgrade-Insecure-Requests": "1",
                        },
                        # その他の回避設定
                        "extractor_retries": 3,
                        "fragment_retries": 3,
                        "file_access_retries": 3,
                        "retry_sleep_functions": {
                            "http": lambda n: min(4 ** n, 60),
                            "fragment": lambda n: min(4 ** n, 60),
                            "file_access": lambda n: min(4 ** n, 60),
                        },
                        # YouTube固有の回避設定
                        "youtube_include_dash_manifest": False,
                        "extractor_args": {
                            "youtube": {
                                "skip": ["hls", "dash"],
                                "player_skip": ["js"],
                                "comment_sort": ["top"],
                                "max_comments": ["0"],
                            }
                        },
                        # ネットワーク設定
                        "socket_timeout": 30,
                        "prefer_insecure": False,
                    }
                    
                    # 時間指定がある場合は安定した方法で処理
                    if start_time is not None or end_time is not None:
                        # 安定したポストプロセッサ方式で時間指定処理
                        st.info(f"✂️ 時間指定処理中: {start_str or '0'}-{end_str or '終了'}")
                        
                        postprocessor_args = []
                        
                        if start_time is not None:
                            postprocessor_args.extend(["-ss", str(start_time)])
                        
                        if end_time is not None:
                            if start_time is not None:
                                duration = end_time - start_time
                                postprocessor_args.extend(["-t", str(duration)])
                            else:
                                postprocessor_args.extend(["-t", str(end_time)])
                        
                        ydl_opts["postprocessors"] = [{
                            "key": "FFmpegVideoRemuxer",
                            "preferedformat": "mp4",
                        }]
                        
                        ydl_opts["postprocessor_args"] = postprocessor_args
                        
                    # ファイル名の生成
                    if start_time is not None or end_time is not None:
                        # 時間指定があるファイル名の生成
                        if start_str and end_str:
                            time_suffix = f"_{start_str}-{end_str}"
                        elif start_str:
                            time_suffix = f"_{start_str}-end"
                        elif end_str:
                            time_suffix = f"_start-{end_str}"
                        else:
                            time_suffix = ""
                        
                        ydl_opts["outtmpl"] = str(out_dir / f"%(title)s{time_suffix}.%(ext)s")
                    else:
                        # 時間指定なしの場合は通常のダウンロード
                        ydl_opts["outtmpl"] = str(out_dir / "%(title)s.%(ext)s")
                    
                    # ダウンロード実行（リトライ機能付き）
                    download_success = False
                    for attempt in range(2):  # 最大2回試行
                        try:
                            with YoutubeDL(ydl_opts) as ydl:
                                if attempt == 1:
                                    # 2回目はさらに回避設定を強化
                                    ydl_opts["sleep_interval"] = 2
                                    ydl_opts["max_sleep_interval"] = 5
                                    st.info(f"🔄 {url}: 再試行中...")
                                
                                ydl.download([url])
                                download_success = True
                                break
                        except Exception as download_error:
                            if attempt == 0 and ("Sign in to confirm" in str(download_error) or "bot" in str(download_error).lower()):
                                import time
                                time.sleep(3)  # 3秒待機
                                continue
                            else:
                                raise download_error
                    
                    if not download_success:
                        raise Exception("複数回の試行後もダウンロードに失敗しました")
                    
                    # ダウンロードしたファイルを session_state に保存
                    try:
                        files_found = False
                        for file_path in out_dir.iterdir():
                            if file_path.is_file() and file_path.suffix.lower() in ['.mp4', '.mkv', '.avi', '.mov', '.webm']:
                                with open(file_path, "rb") as f:
                                    st.session_state["files"].append((file_path.name, f.read()))
                                file_path.unlink()  # 一時ファイルを削除
                                files_found = True
                        
                        if not files_found:
                            st.warning(f"⚠️ {url}: ダウンロードされたファイルが見つかりませんでした")
                    except Exception as file_error:
                        st.error(f"ファイル処理エラー: {file_error}")
                
                except Exception as e:
                    error_msg = str(e)
                    if "Sign in to confirm" in error_msg or "bot" in error_msg.lower():
                        st.warning(f"⚠️ {url}: YouTubeのbot検出によりアクセスが制限されています。少し待ってから再試行してください。")
                    elif "No video formats found" in error_msg:
                        st.error(f"⚠️ {url}: 動画フォーマットが見つかりません。非公開または制限付きの動画の可能性があります。")
                    elif "Private video" in error_msg:
                        st.error(f"🔒 {url}: 非公開動画のためアクセスできません。")
                    elif "Video unavailable" in error_msg:
                        st.error(f"🚫 {url}: 動画が利用できません。削除されたか、地域制限がある可能性があります。")
                    else:
                        st.error(f"❌ {url} でエラー: {e}")
                    continue

    if st.session_state["files"]:
        st.success("ダウンロード準備が完了しました！下のボタンから保存してください。")
    else:
        st.error("ダウンロードに失敗しました。URLと時間指定を確認してください。")

# ------------------------------------------------------------------
# ② session_state にファイルがあれば、常にボタンを描画
#    （画面が再実行されても消えない）
# ------------------------------------------------------------------
if "files" in st.session_state:
    st.markdown("---")
    st.subheader("ダウンロードファイル")
    for name, data in st.session_state["files"]:
        st.download_button(
            label=f"⬇️ {name}",
            data=data,
            file_name=name,
            mime="video/mp4",
            key=f"dl_{name}",          # キーをユニークにする
        )