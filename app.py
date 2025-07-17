import streamlit as st
from yt_dlp import YoutubeDL
from pathlib import Path
from tempfile import TemporaryDirectory
import shutil
import re

# アプリケーションのバージョン情報
APP_VERSION = "v1.0.0"
APP_NAME = "YouTube Video Downloader"
LAST_UPDATED = "2025-01-17"

# ヘッダー部分
col1, col2 = st.columns([3, 1])
with col1:
    st.title(APP_NAME)
with col2:
    st.markdown(f"""
    <div style="text-align: right; margin-top: 20px;">
        <span style="background-color: #0066cc; color: white; padding: 4px 8px; border-radius: 4px; font-size: 12px;">
            {APP_VERSION}
        </span><br>
        <small style="color: #666; font-size: 10px;">Updated: {LAST_UPDATED}</small>
    </div>
    """, unsafe_allow_html=True)


# アプリケーション情報表示
with st.expander("📊 アプリ情報"):
    st.markdown(f"""
    **バージョン**: {APP_VERSION} | **更新日**: {LAST_UPDATED}
    
    **v1.0.0** - 一括ダウンロード機能
    - 📦 YouTube動画の一括ダウンロード機能
    """)

# ── 一括ダウンロード ───────────────────────────────────
st.subheader("一括ダウンロード")
st.write("複数のYouTube URLを1行につき1つずつ貼り付けて、一括でダウンロードできます。")

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
if bulk_download:
    # 入力検証
    urls = [u.strip() for u in bulk_urls.splitlines() if u.strip()]
    
    if not urls:
        st.warning("URL が入力されていません")
        st.stop()
    
    with st.spinner(f"{len(urls)} 本をダウンロード中…"):
        with TemporaryDirectory() as td:
            out_dir = Path(td)
            
            st.session_state["files"] = []
            
            for url in urls:
                try:
                    # 基本のyt-dlpオプション
                    ydl_opts = {
                        "format": (
                            "bestvideo[ext=mp4][height<=1080]+"
                            "bestaudio[ext=m4a]/best[ext=mp4][height<=1080]"
                        ),
                        "merge_output_format": "mp4",
                        "quiet": True,
                        "outtmpl": str(out_dir / "%(title)s.%(ext)s")
                    }
                    
                    # ダウンロード実行
                    with YoutubeDL(ydl_opts) as ydl:
                        ydl.download([url])
                    
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
                    if "No video formats found" in error_msg:
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
        st.error("ダウンロードに失敗しました。URLを確認してください。")

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

# フッター部分
st.markdown("---")
col1, col2, col3 = st.columns([1, 2, 1])
with col2:
    st.markdown(f"""
    <div style="text-align: center; color: #666; font-size: 12px; padding: 10px;">
        <strong>{APP_NAME}</strong> {APP_VERSION}<br>
        📦 Simple YouTube bulk downloader<br>
        <small>Last updated: {LAST_UPDATED} | Built with Streamlit & yt-dlp</small>
    </div>
    """, unsafe_allow_html=True)