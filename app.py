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

    if shutil.which("ffmpeg") is None:
        st.error(
            "ffmpeg が見つかりません。\n"
            "ローカルの場合はインストールしてください。\n"
            "Streamlit Cloud では packages.txt に 'ffmpeg' と書いておけば自動導入されます。"
        )
        st.stop()

    mode_text = "個別指定" if download_mode == "individual" else "一括"
    with st.spinner(f"{len(valid_entries)} 本を{mode_text}ダウンロード中…"):
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
                    # 基本のyt-dlpオプション
                    ydl_opts = {
                        "format": (
                            "bestvideo[ext=mp4][height<=1080]+"
                            "bestaudio[ext=m4a]/best[ext=mp4][height<=1080]"
                        ),
                        "merge_output_format": "mp4",
                        "quiet": True,
                    }
                    
                    # 時間指定がある場合はffmpegで切り出し
                    if start_time is not None or end_time is not None:
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
                        ydl_opts["outtmpl"] = str(out_dir / "%(title)s.%(ext)s")
                    
                    with YoutubeDL(ydl_opts) as ydl:
                        ydl.download([url])
                    
                    # ダウンロードしたファイルを session_state に保存
                    for fp in out_dir.iterdir():
                        if fp.is_file() and fp.suffix.lower() in ['.mp4', '.mkv', '.avi', '.mov']:
                            with open(fp, "rb") as f:
                                st.session_state["files"].append((fp.name, f.read()))
                            fp.unlink()  # 一時ファイルを削除
                
                except Exception as e:
                    st.error(f"{url} でエラー: {e}")
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