import os, io, fitz, zipfile, shutil, threading
import tkinter as tk
from tkinter import filedialog, ttk, messagebox
from PIL import Image, ImageTk

VERSION = "1.0.0"
TITLE = "📘 PDF → CBZ 转换器"

# ================== 模式定义（含说明） ==================
MODES = {
    "高质量（大文件）": {
        "dpi": 200,
        "quality": 90,
        "grayscale": False,
        "desc": "适用于杂志、画册、漫画、彩页等需要保真图像的文档。",
    },
    "标准（推荐）": {
        "dpi": 150,
        "quality": 80,
        "grayscale": False,
        "desc": "适用于一般电子书、报告、课程讲义等常规文档。",
    },
    "小体积（快速）": {
        "dpi": 100,
        "quality": 70,
        "grayscale": False,
        "desc": "适用于纯文字文档、说明书、扫描件，追求更小文件体积。",
    },
    "黑白文档（最小）": {
        "dpi": 100,
        "quality": 70,
        "grayscale": True,
        "desc": "适用于黑白扫描文档、论文、OCR 识别等。",
    },
}


class PDF2CBZApp:
    def __init__(self, root):
        self.root = root
        self.root.title(TITLE + " v" + VERSION)
        self.root.geometry("780x420")

        # === 图标 ===
        icon_path = os.path.join(os.path.dirname(__file__), "app.png")
        if os.path.exists(icon_path):
            try:
                icon_img = Image.open(icon_path)
                self.app_icon = ImageTk.PhotoImage(icon_img)
                self.root.iconphoto(True, self.app_icon)
            except Exception:
                pass

        # === 状态变量 ===
        self.input_path = tk.StringVar(value="")
        self.output_dir = tk.StringVar(value=os.getcwd())
        self.keep_jpg = tk.BooleanVar(value=False)
        self.mode_var = tk.StringVar(value="标准（推荐）")
        self.file_mode = tk.BooleanVar(value=False)
        self.pdf_paths = []
        self.output_manually_set = False  # ✅ 记录是否手动设置输出目录

        # ===== 输入路径 =====
        frm_in = tk.Frame(root)
        frm_in.pack(fill="x", padx=10, pady=5)
        tk.Label(frm_in, text="输入路径：").pack(side=tk.LEFT)
        tk.Entry(frm_in, textvariable=self.input_path, width=55).pack(
            side=tk.LEFT, padx=5
        )
        tk.Button(frm_in, text="浏览", command=self.select_input).pack(
            side=tk.LEFT, padx=2
        )
        tk.Checkbutton(frm_in, text="文件模式", variable=self.file_mode).pack(
            side=tk.LEFT, padx=5
        )

        # ===== 输出路径 =====
        frm_out = tk.Frame(root)
        frm_out.pack(fill="x", padx=10, pady=5)
        tk.Label(frm_out, text="输出目录：").pack(side=tk.LEFT)
        tk.Entry(frm_out, textvariable=self.output_dir, width=55).pack(
            side=tk.LEFT, padx=5
        )
        tk.Button(frm_out, text="浏览", command=self.select_output_dir).pack(
            side=tk.LEFT
        )

        # ===== 压缩模式 + 说明 + 保留JPG =====
        frm_opt = tk.Frame(root)
        frm_opt.pack(fill="x", padx=10, pady=8, anchor="w")

        tk.Label(frm_opt, text="压缩模式:").pack(side=tk.LEFT, padx=(0, 5))
        self.combo_mode = ttk.Combobox(
            frm_opt,
            textvariable=self.mode_var,
            values=list(MODES.keys()),
            width=16,
            state="readonly",
        )
        self.combo_mode.pack(side=tk.LEFT, padx=5)
        self.combo_mode.bind("<<ComboboxSelected>>", self.update_mode_hint)

        # 模式说明同行显示
        self.label_mode_hint = tk.Label(
            frm_opt,
            text="",
            fg="#0066CC",
            justify="left",
            wraplength=420,
            anchor="w",
            font=("Arial", 12),
        )
        self.label_mode_hint.pack(side=tk.LEFT, padx=10)

        # 保留JPG
        tk.Checkbutton(frm_opt, text="保留 JPG 文件夹", variable=self.keep_jpg).pack(
            side=tk.LEFT, padx=15
        )

        # ===== 转换按钮单独一行居中 =====
        frm_btn = tk.Frame(root)
        frm_btn.pack(fill="x", pady=5)
        tk.Button(
            frm_btn, text="开始转换", command=self.start_conversion, width=18, height=1
        ).pack(anchor="center")

        # ===== 状态栏（蓝色，字号=12） =====
        self.label_status = tk.Label(
            root, text="等待开始...", fg="#0066CC", anchor="w", font=("Arial", 12)
        )
        self.label_status.pack(fill="x", padx=10, pady=(3, 0))

        # ===== 进度条 =====
        frm_progress = tk.Frame(root)
        frm_progress.pack(fill="x", padx=10, pady=2)
        tk.Label(frm_progress, text="📂 当前批次进度：", anchor="w").pack(anchor="w")
        self.progress_all = ttk.Progressbar(
            frm_progress, orient="horizontal", mode="determinate"
        )
        self.progress_all.pack(fill="x", padx=0, pady=2)
        tk.Label(frm_progress, text="📄 当前文件进度：", anchor="w").pack(
            anchor="w", pady=(5, 0)
        )
        self.progress_file = ttk.Progressbar(
            frm_progress, orient="horizontal", mode="determinate"
        )
        self.progress_file.pack(fill="x", padx=0, pady=2)

        # ===== 日志区域 =====
        self.text_log = tk.Text(root, height=8, bg="#f8f8f8", state="disabled")
        self.text_log.pack(fill="both", expand=True, padx=10, pady=8)

        # 初始化提示
        self.update_mode_hint()

    # ========== 模式说明更新 ==========
    def update_mode_hint(self, event=None):
        mode = self.mode_var.get()
        desc = MODES.get(mode, {}).get("desc", "")
        self.label_mode_hint.config(text=f"💡 {desc}")

    # ========== 输入路径 ==========
    def select_input(self):
        if self.file_mode.get():
            path = filedialog.askopenfilename(
                title="选择 PDF 文件",
                filetypes=[("PDF 文件", "*.pdf")],
                initialdir=os.getcwd(),
            )
            if not path:
                return
            self.input_path.set(path)
            self.pdf_paths = [path]
            self.log(f"📄 已选中单个 PDF 文件：{os.path.basename(path)}")
            new_dir = os.path.dirname(path)
        else:
            path = filedialog.askdirectory(
                title="选择包含 PDF 的文件夹", initialdir=os.getcwd()
            )
            if not path:
                return
            self.input_path.set(path)
            self.pdf_paths = [
                os.path.join(path, f)
                for f in os.listdir(path)
                if f.lower().endswith(".pdf")
            ]
            self.log(f"📂 目录中检测到 {len(self.pdf_paths)} 个 PDF 文件。")
            new_dir = path

        # ✅ 若用户未手动修改输出路径，则同步为输入路径
        if not self.output_manually_set:
            self.output_dir.set(new_dir)
            self.log(f"📁 输出目录自动设置为：{new_dir}")

    # ========== 输出路径 ==========
    def select_output_dir(self):
        path = filedialog.askdirectory(title="选择输出目录", initialdir=os.getcwd())
        if path:
            self.output_dir.set(path)
            self.output_manually_set = True  # ✅ 标记为手动设置
            self.log(f"📁 输出目录设置为：{path}")

    # ========== 启动转换 ==========
    def start_conversion(self):
        if not self.pdf_paths:
            messagebox.showwarning("提示", "请先选择输入文件或目录。")
            return
        mode = MODES[self.mode_var.get()]
        self.log(f"⚙️ 当前模式：{self.mode_var.get()} — {mode['desc']}")
        threading.Thread(target=self.convert_all, daemon=True).start()

    # ========== 批量转换 ==========
    def convert_all(self):
        mode = MODES[self.mode_var.get()]
        total = len(self.pdf_paths)
        self.progress_all["maximum"] = total
        self.progress_all["value"] = 0

        for idx, pdf in enumerate(self.pdf_paths, start=1):
            self.label_status.config(
                text=f"📘 ({idx}/{total}) 正在转换：{os.path.basename(pdf)}",
                fg="#0066CC",
            )
            self.convert_single(pdf, mode)
            self.progress_all["value"] = idx
            self.root.update_idletasks()

        self.label_status.config(text="🎉 全部任务完成！", fg="#0066CC")
        self.log("✅ 所有 PDF 转换完成。")

    # ========== 单个文件 ==========
    def convert_single(self, pdf_path, mode):
        dpi, quality, gray = mode["dpi"], mode["quality"], mode["grayscale"]
        basename = os.path.splitext(os.path.basename(pdf_path))[0]
        outdir = os.path.join(self.output_dir.get(), basename + "_jpg")
        cbzfile = os.path.join(self.output_dir.get(), basename + ".cbz")
        os.makedirs(outdir, exist_ok=True)

        try:
            doc = fitz.open(pdf_path)
        except Exception as e:
            self.log(f"❌ 无法打开 {pdf_path}: {e}")
            return

        total_pages = len(doc)
        self.progress_file["maximum"] = total_pages
        self.progress_file["value"] = 0
        self.log(
            f"🌀 {basename} - 共 {total_pages} 页 (DPI={dpi}, 质量={quality}, 灰度={gray})"
        )

        for i, page in enumerate(doc, start=1):
            zoom = dpi / 72
            mat = fitz.Matrix(zoom, zoom)
            pix = page.get_pixmap(matrix=mat)

            # 去除 alpha 通道
            if pix.alpha:
                pix = fitz.Pixmap(pix, 0)

            # 转 PIL 以支持 quality 参数
            img_bytes = pix.tobytes("png")
            img = Image.open(io.BytesIO(img_bytes))
            if gray:
                img = img.convert("L")

            out_path = os.path.join(outdir, f"page-{i}.jpg")
            img.save(
                out_path, format="JPEG", quality=quality, optimize=True, subsampling=1
            )

            self.progress_file["value"] = i
            self.label_status.config(
                text=f"📄 {basename} 第 {i}/{total_pages} 页...", fg="#0066CC"
            )
            self.root.update_idletasks()

        doc.close()
        self.log("📦 打包 CBZ...")
        with zipfile.ZipFile(cbzfile, "w", zipfile.ZIP_DEFLATED) as zf:
            for f in sorted(os.listdir(outdir)):
                zf.write(os.path.join(outdir, f), f)
        self.log(f"✅ 已生成: {cbzfile}")

        if not self.keep_jpg.get():
            shutil.rmtree(outdir)
            self.log("🧹 已删除 JPG 文件夹")

    # ========== 日志 ==========
    def log(self, msg):
        self.text_log.config(state="normal")
        self.text_log.insert("end", msg + "\n")
        self.text_log.see("end")
        self.text_log.config(state="disabled")
        self.root.update_idletasks()


if __name__ == "__main__":
    root = tk.Tk()
    app = PDF2CBZApp(root)
    root.mainloop()
