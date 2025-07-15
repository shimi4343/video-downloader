import streamlit as st
from yt_dlp import YoutubeDL
from pathlib import Path
from tempfile import TemporaryDirectory
import shutil

st.title("YouTube Bulk Downloader (1080p MP4)")

# ── URL 入力欄 ───────────────────────────────────
url_text = st.text_area(
    "1 行に 1 つずつ YouTube URL を貼り付けてください",
    height=150,
    placeholder="https://youtu.be/...\nhttps://www.youtube.com/watch?v=..."
)

# ── Download ボタン ─────────────────────────────
run_dl = st.button("Download")

# ------------------------------------------------------------------
# ① Download ボタンが押されたときだけ動画を取得して session_state に保存
# ------------------------------------------------------------------
if run_dl:
    urls = [u.strip() for u in url_text.splitlines() if u.strip()]
    if not urls:
        st.warning("URL が入力されていません")
        st.stop()

    if shutil.which("ffmpeg") is None:
        st.error(
            "ffmpeg が見つかりません。\n"
            "ローカルの場合はインストールしてください。\n"
            "Streamlit Cloud では packages.txt に 'ffmpeg' と書いておけば自動導入されます。"
        )
        st.stop()

    with st.spinner(f"{len(urls)} 本をダウンロード中…"):
        with TemporaryDirectory() as td:
            out_dir = Path(td)

            ydl_opts = {
                "format": (
                    "bestvideo[ext=mp4][height<=1080]+"
                    "bestaudio[ext=m4a]/best[ext=mp4][height<=1080]"
                ),
                "merge_output_format": "mp4",
                "outtmpl": str(out_dir / "%(title)s.%(ext)s"),
                "quiet": True,
            }

            for url in urls:
                try:
                    with YoutubeDL(ydl_opts) as ydl:
                        ydl.download([url])
                except Exception as e:
                    st.error(f"{url} でエラー: {e}")

            # ---- 取得したファイルを session_state に保持 ----
            st.session_state["files"] = []
            for fp in out_dir.iterdir():
                with open(fp, "rb") as f:
                    st.session_state["files"].append((fp.name, f.read()))

    st.success("ダウンロード準備が完了しました！下のボタンから保存してください。")

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