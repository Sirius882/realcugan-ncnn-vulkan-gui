import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import subprocess
import threading
import os
import sys


class ToolTip:
    """鼠标悬停提示框"""
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tooltip = None
        self.widget.bind('<Enter>', self.show)
        self.widget.bind('<Leave>', self.hide)
    
    def show(self, event=None):
        x, y, _, _ = self.widget.bbox("insert")
        x += self.widget.winfo_rootx() + 25
        y += self.widget.winfo_rooty() + 25
        
        self.tooltip = tk.Toplevel(self.widget)
        self.tooltip.wm_overrideredirect(True)
        self.tooltip.wm_geometry(f"+{x}+{y}")
        
        label = tk.Label(self.tooltip, text=self.text, 
                        background="#333333", foreground="white",
                        relief=tk.SOLID, borderwidth=1,
                        font=("Microsoft YaHei UI", 9), 
                        padx=8, pady=5, wraplength=300)
        label.pack()
    
    def hide(self, event=None):
        if self.tooltip:
            self.tooltip.destroy()
            self.tooltip = None


class RealCUGANGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Real-CUGAN 图像增强工具")
        self.root.geometry("900x750")
        self.root.resizable(True, True)
        
        # 设置样式
        style = ttk.Style()
        style.theme_use('clam')
        
        # 变量
        self.verbose = tk.BooleanVar(value=False)
        self.input_path = tk.StringVar()
        self.output_path = tk.StringVar()
        self.noise_level = tk.StringVar(value='-1')
        self.scale = tk.StringVar(value='2')
        self.syncgap = tk.StringVar(value='3')
        self.model_path = tk.StringVar(value='models-se')
        self.tta_mode = tk.BooleanVar(value=False)
        self.format_var = tk.StringVar(value='png')
        
        # 创建界面
        self.create_widgets()
        
        # 保存scale combobox的引用，用于后续更新
        self.scale_combo = None
        
        # 绑定变量变化事件
        for var in [self.verbose, self.input_path, self.output_path, 
                   self.noise_level, self.scale, self.syncgap, 
                   self.model_path, self.tta_mode, self.format_var]:
            var.trace_add('write', lambda *args: self.update_command())
        
        # 绑定模型变化事件，用于更新可用的倍率选项
        self.model_path.trace_add('write', lambda *args: self.update_scale_options())
        
        self.update_command()
    
    def create_widgets(self):
        # 主容器
        main_frame = ttk.Frame(self.root, padding="15")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        
        # 标题
        title_frame = ttk.Frame(main_frame)
        title_frame.grid(row=0, column=0, columnspan=2, pady=(0, 15), sticky=tk.W)
        
        title_label = tk.Label(title_frame, text="🖼 Real-CUGAN 图像增强工具", 
                              font=("Microsoft YaHei UI", 16, "bold"),
                              fg="#2563eb")
        title_label.pack(side=tk.LEFT)
        
        # 左侧面板
        left_frame = ttk.LabelFrame(main_frame, text="基础设置", padding="10")
        left_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(0, 5))
        
        # 右侧面板
        right_frame = ttk.LabelFrame(main_frame, text="高级设置", padding="10")
        right_frame.grid(row=1, column=1, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(5, 0))
        
        main_frame.columnconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(1, weight=1)
        
        # === 左侧面板内容 ===
        # 采用 grid 布局，每个控件占两行：label 行 + 控件行
        row = 0

        # 输入路径
        self.create_path_input(left_frame, row, "输入路径 (-i)", self.input_path,
                              "输入图像文件路径（支持 jpg/png/webp）或文件夹路径",
                              is_output=False)
        row += 2

        # 输出路径
        self.create_path_input(left_frame, row, "输出路径 (-o)", self.output_path,
                              "输出图像文件路径或文件夹路径",
                              is_output=True)
        row += 2

        # 降噪级别
        self.create_dropdown(left_frame, row, "降噪级别 (-n)", self.noise_level,
                           [('-1', '-1 (无降噪)'),
                            ('0', '0 (轻度降噪)'),
                            ('1', '1 (中度降噪)'),
                            ('2', '2 (较强降噪)'),
                            ('3', '3 (强力降噪)')],
                           "降噪强度等级，数值越大降噪效果越强，-1 表示不降噪")
        row += 2

        # 放大倍数
        self.scale_options_all = {
            'models-se': [('1', '1x (不放大)'), ('2', '2x (默认)'), ('3', '3x'), ('4', '4x')],
            'models-pro': [('1', '1x (不放大)'), ('2', '2x (默认)'), ('3', '3x')],
            'models-nose': [('1', '1x (不放大)'), ('2', '2x (默认)')]
        }

        self.scale_combo = self.create_dropdown(left_frame, row, "放大倍数 (-s)", self.scale,
                           self.scale_options_all['models-se'],
                           "图像放大倍数，1 表示不放大，2 表示放大到原图的2倍\n注意：可用倍率取决于所选模型")
        row += 2
        
        # === 右侧面板内容 ===
        row = 0

        # 同步间隔模式
        self.create_dropdown(right_frame, row, "同步间隔模式 (-c)", self.syncgap,
                           [('0', '0 (不同步)'),
                            ('1', '1 (精确同步)'),
                            ('2', '2 (粗略同步)'),
                            ('3', '3 (非常粗略，默认)')],
                           "GPU 同步模式，影响处理速度和显存占用，默认值通常效果最好")
        row += 2

        # 模型路径
        self.create_dropdown(right_frame, row, "模型路径 (-m)", self.model_path,
                           [('models-se', 'models-se (标准版)'),
                            ('models-pro', 'models-pro (专业版)'),
                            ('models-nose', 'models-nose (无降噪版)')],
                           "选择使用的 AI 模型，se 为标准版，支持1~4倍，pro 质量更高但速度较慢，支持1~3倍，nose 适合无需降噪的图像，支持1~2倍")
        row += 2

        # 输出格式
        self.create_dropdown(right_frame, row, "输出格式 (-f)", self.format_var,
                           [('png', 'PNG (默认，无损)'),
                            ('jpg', 'JPG (有损压缩)'),
                            ('webp', 'WEBP (更小体积)')],
                           "输出图像的文件格式，PNG 质量最好但文件较大，WEBP 文件最小")
        row += 2

        # 复选框选项（使用 grid 而非 pack，避免与 grid 混用）
        checkbox_frame = ttk.Frame(right_frame)
        checkbox_frame.grid(row=row, column=0, columnspan=3, pady=(15, 0), sticky=(tk.W, tk.E))
        checkbox_frame.columnconfigure(0, weight=1)

        # TTA 模式
        tta_cb = ttk.Checkbutton(checkbox_frame, text="TTA 模式 (-x)", variable=self.tta_mode)
        tta_cb.grid(row=0, column=0, sticky=tk.W, pady=3)
        tta_info = tk.Label(checkbox_frame, text="ℹ", fg="#3b82f6", cursor="hand2", font=("Arial", 10, "bold"))
        tta_info.grid(row=0, column=1, sticky=tk.W, padx=(5, 0))
        ToolTip(tta_info, "测试时增强模式，可提高输出质量但处理时间会显著增加（约8倍）")
        
        # 命令预览区域
        command_frame = ttk.LabelFrame(main_frame, text="生成的命令行", padding="10")
        command_frame.grid(row=2, column=0, columnspan=2, pady=(15, 10), sticky=(tk.W, tk.E))
        
        self.command_text = scrolledtext.ScrolledText(command_frame, height=3, 
                                                     wrap=tk.WORD, 
                                                     font=("Consolas", 9))
        self.command_text.pack(fill=tk.BOTH, expand=True)
        
        # 按钮区域
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=3, column=0, columnspan=2, pady=(10, 0))
        
        start_btn = tk.Button(button_frame, text="▶ 开始处理", 
                             command=self.start_processing,
                             bg="#2563eb", fg="white", 
                             font=("Microsoft YaHei UI", 10, "bold"),
                             padx=20, pady=8, cursor="hand2",
                             relief=tk.FLAT, borderwidth=0)
        start_btn.pack(side=tk.LEFT, padx=5)
        
        copy_btn = tk.Button(button_frame, text="📋 复制命令", 
                            command=self.copy_command,
                            bg="#6b7280", fg="white", 
                            font=("Microsoft YaHei UI", 10),
                            padx=20, pady=8, cursor="hand2",
                            relief=tk.FLAT, borderwidth=0)
        copy_btn.pack(side=tk.LEFT, padx=5)
        
        # 使用说明
        info_frame = ttk.LabelFrame(main_frame, text="使用说明", padding="10")
        info_frame.grid(row=4, column=0, columnspan=2, pady=(10, 0), sticky=(tk.W, tk.E))
        
        info_text = """• 本工具为 Real-CUGAN 的图形界面版本
• 支持批量处理：输入/输出路径填写文件夹即可
• 鼠标悬停在 ℹ 图标上可查看详细说明
• 推荐首次使用时保持默认参数设置
• 确保 realcugan-ncnn-vulkan.exe 在系统 PATH 中或与本程序在同一目录"""
        
        info_label = tk.Label(info_frame, text=info_text, 
                             justify=tk.LEFT, fg="#1e40af",
                             font=("Microsoft YaHei UI", 9))
        info_label.pack(anchor=tk.W)
    
    def create_path_input(self, parent, row, label, variable, tooltip, is_output=False):
        """创建路径输入控件"""
        label_frame = ttk.Frame(parent)
        label_frame.grid(row=row, column=0, columnspan=3, pady=(5, 2), sticky=tk.W)

        lbl = ttk.Label(label_frame, text=label, font=("Microsoft YaHei UI", 9, "bold"))
        lbl.grid(row=0, column=0, sticky=tk.W)

        info_label = tk.Label(label_frame, text="ℹ", fg="#3b82f6", 
                             cursor="hand2", font=("Arial", 10, "bold"))
        info_label.grid(row=0, column=1, sticky=tk.W, padx=(5, 0))
        ToolTip(info_label, tooltip)

        input_frame = ttk.Frame(parent)
        input_frame.grid(row=row+1, column=0, columnspan=3, pady=(0, 10), sticky=(tk.W, tk.E))
        parent.columnconfigure(0, weight=1)
        input_frame.columnconfigure(0, weight=1)

        entry = ttk.Entry(input_frame, textvariable=variable)
        entry.grid(row=0, column=0, sticky=(tk.W, tk.E), padx=(0, 5))

        browse_btn = ttk.Button(input_frame, text="📁 浏览", 
                               command=lambda: self.browse_path(variable, is_output))
        browse_btn.grid(row=0, column=1)
    
    def create_dropdown(self, parent, row, label, variable, options, tooltip):
        """创建下拉菜单控件"""
        label_frame = ttk.Frame(parent)
        label_frame.grid(row=row, column=0, columnspan=3, pady=(5, 2), sticky=tk.W)

        lbl = ttk.Label(label_frame, text=label, font=("Microsoft YaHei UI", 9, "bold"))
        lbl.grid(row=0, column=0, sticky=tk.W)

        info_label = tk.Label(label_frame, text="ℹ", fg="#3b82f6", 
                             cursor="hand2", font=("Arial", 10, "bold"))
        info_label.grid(row=0, column=1, sticky=tk.W, padx=(5, 0))
        ToolTip(info_label, tooltip)

        combo = ttk.Combobox(parent, textvariable=variable, 
                            values=[opt[1] for opt in options],
                            state='readonly')
        combo.grid(row=row+1, column=0, columnspan=3, pady=(0, 10), sticky=(tk.W, tk.E))
        parent.columnconfigure(0, weight=1)

        # 创建值到显示文本的映射字典
        combo.value_display_map = {value: display for value, display in options}
        combo.display_value_map = {display: value for value, display in options}

        # 设置初始显示值
        if variable.get() in combo.value_display_map:
            combo.set(combo.value_display_map[variable.get()])

        # 绑定选择事件
        def on_select(event):
            selected_display = combo.get()
            if selected_display in combo.display_value_map:
                selected_value = combo.display_value_map[selected_display]
                variable.set(selected_value)

        combo.bind('<<ComboboxSelected>>', on_select)

        # 返回combobox引用，以便后续更新
        return combo
    
    def browse_path(self, variable, is_output):
        """浏览文件或文件夹"""
        # 创建自定义选择对话框
        dialog = tk.Toplevel(self.root)
        dialog.title("选择路径类型")
        dialog.geometry("320x150")
        dialog.transient(self.root)
        dialog.grab_set()
        
        # 居中显示
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - (dialog.winfo_width() // 2)
        y = (dialog.winfo_screenheight() // 2) - (dialog.winfo_height() // 2)
        dialog.geometry(f"+{x}+{y}")
        
        result = {'choice': None}
        
        label = tk.Label(dialog, 
                        text="请选择路径类型：" if not is_output else "请选择输出路径类型：",
                        font=("Microsoft YaHei UI", 10),
                        pady=15)
        label.pack()
        
        button_frame = ttk.Frame(dialog)
        button_frame.pack(pady=10)
        
        def choose_file():
            result['choice'] = 'file'
            dialog.destroy()
        
        def choose_folder():
            result['choice'] = 'folder'
            dialog.destroy()
        
        file_btn = tk.Button(button_frame, 
                            text="📄 选择文件" if not is_output else "💾 保存为文件",
                            command=choose_file,
                            bg="#3b82f6", fg="white",
                            font=("Microsoft YaHei UI", 10),
                            padx=15, pady=8,
                            cursor="hand2",
                            relief=tk.FLAT)
        file_btn.pack(side=tk.LEFT, padx=5)
        
        folder_btn = tk.Button(button_frame, 
                              text="📁 选择文件夹",
                              command=choose_folder,
                              bg="#10b981", fg="white",
                              font=("Microsoft YaHei UI", 10),
                              padx=15, pady=8,
                              cursor="hand2",
                              relief=tk.FLAT)
        folder_btn.pack(side=tk.LEFT, padx=5)
        
        cancel_btn = tk.Button(button_frame,
                              text="❌ 取消",
                              command=dialog.destroy,
                              bg="#6b7280", fg="white",
                              font=("Microsoft YaHei UI", 10),
                              padx=15, pady=8,
                              cursor="hand2",
                              relief=tk.FLAT)
        cancel_btn.pack(side=tk.LEFT, padx=5)
        
        # 等待对话框关闭
        self.root.wait_window(dialog)
        
        # 根据选择打开相应的文件对话框
        path = None
        if result['choice'] == 'file':
            if is_output:
                path = filedialog.asksaveasfilename(
                    title="保存输出文件",
                    defaultextension=".png",
                    filetypes=[("PNG files", "*.png"), 
                              ("JPG files", "*.jpg"), 
                              ("WEBP files", "*.webp"),
                              ("All files", "*.*")])
            else:
                path = filedialog.askopenfilename(
                    title="选择输入图片文件",
                    filetypes=[("图像文件", "*.jpg *.jpeg *.png *.webp"),
                              ("JPG files", "*.jpg *.jpeg"),
                              ("PNG files", "*.png"),
                              ("WEBP files", "*.webp"),
                              ("所有文件", "*.*")])
        elif result['choice'] == 'folder':
            path = filedialog.askdirectory(
                title="选择输出文件夹" if is_output else "选择输入文件夹")
        
        if path:
            variable.set(path)
    
    def update_scale_options(self):
        """根据选择的模型更新可用的放大倍率"""
        if not self.scale_combo:
            return
        
        current_model = self.model_path.get()
        current_scale = self.scale.get()
        
        # 获取当前模型支持的倍率选项
        if current_model in self.scale_options_all:
            options = self.scale_options_all[current_model]
        else:
            options = self.scale_options_all['models-se']
            
        # 更新映射字典
        self.scale_combo.value_display_map = {value: display for value, display in options}
        self.scale_combo.display_value_map = {display: value for value, display in options}
        
        # 更新下拉菜单的选项
        self.scale_combo['values'] = [opt[1] for opt in options]
        
        # 检查当前选择的倍率是否在新选项中
        available_scales = [opt[0] for opt in options]
        if current_scale not in available_scales:
            # 如果当前倍率不可用，设置为默认值2（如果可用），否则设置为第一个可用值
            if '2' in available_scales:
                self.scale.set('2')
                if '2' in self.scale_combo.value_display_map:
                    self.scale_combo.set(self.scale_combo.value_display_map['2'])
            else:
                self.scale.set(available_scales[0])
                self.scale_combo.set(options[0][1])
        else:
            # 更新显示值
            if current_scale in self.scale_combo.value_display_map:
                self.scale_combo.set(self.scale_combo.value_display_map[current_scale])
                    
        # 强制更新下拉菜单
        self.scale_combo.update()
    
    def update_command(self):
        """更新命令预览"""
        cmd = 'realcugan-ncnn-vulkan'

        # 必须参数
        if self.verbose.get():
            cmd += ' -v'
        if self.input_path.get():
            cmd += f' -i "{self.input_path.get()}"'
        if self.output_path.get():
            cmd += f' -o "{self.output_path.get()}"'

        # 只在非默认值时添加参数
        noise_val = self.noise_level.get().split()[0]
        if noise_val != '-1':
            cmd += f' -n {noise_val}'

        scale_val = self.scale.get().split('x')[0].strip()
        if scale_val != '2':
            cmd += f' -s {scale_val}'

        syncgap_val = self.syncgap.get().split()[0]
        if syncgap_val != '3':
            cmd += f' -c {syncgap_val}'

        model_val = self.model_path.get().split()[0]
        if model_val != 'models-se':
            cmd += f' -m {model_val}'

        if self.tta_mode.get():
            cmd += ' -x'

        format_val = self.format_var.get().split()[0].lower()
        if format_val != 'png':
            cmd += f' -f {format_val}'

        self.command_text.delete(1.0, tk.END)
        self.command_text.insert(1.0, cmd)
    
    def copy_command(self):
        """复制命令到剪贴板"""
        command = self.command_text.get(1.0, tk.END).strip()
        self.root.clipboard_clear()
        self.root.clipboard_append(command)
        messagebox.showinfo("成功", "命令已复制到剪贴板！")
    
    def start_processing(self):
        """开始处理"""
        if not self.input_path.get():
            messagebox.showerror("错误", "请先设置输入路径！")
            return
        if not self.output_path.get():
            messagebox.showerror("错误", "请先设置输出路径！")
            return
        
        # 在新线程中执行命令
        def run_command():
            try:
                command = self.command_text.get(1.0, tk.END).strip()
                
                # 创建进度窗口
                progress_window = tk.Toplevel(self.root)
                progress_window.title("处理中...")
                progress_window.geometry("500x300")
                progress_window.transient(self.root)
                
                label = tk.Label(progress_window, text="正在处理，请稍候...", 
                               font=("Microsoft YaHei UI", 10))
                label.pack(pady=10)
                
                output_text = scrolledtext.ScrolledText(progress_window, height=15, 
                                                       font=("Consolas", 9))
                output_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
                
                # 执行命令
                process = subprocess.Popen(
                    command,
                    shell=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    encoding='utf-8',
                    errors='ignore'
                )
                
                # 实时显示输出
                for line in process.stdout:
                    output_text.insert(tk.END, line)
                    output_text.see(tk.END)
                    output_text.update()
                
                process.wait()
                
                if process.returncode == 0:
                    output_text.insert(tk.END, "\n\n✅ 处理完成！\n")
                    messagebox.showinfo("成功", "图像处理完成！")
                else:
                    output_text.insert(tk.END, f"\n\n❌ 处理失败，返回码: {process.returncode}\n")
                    messagebox.showerror("错误", f"处理失败！返回码: {process.returncode}")
                
            except FileNotFoundError:
                messagebox.showerror("错误", 
                    "找不到 realcugan-ncnn-vulkan.exe！\n\n"
                    "请确保程序在系统 PATH 中或与本程序在同一目录。")
            except Exception as e:
                messagebox.showerror("错误", f"执行出错：{str(e)}")
        
        thread = threading.Thread(target=run_command, daemon=True)
        thread.start()


def main():
    # 高DPI适配（Windows专用）
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)  # 1: 系统感知, 2: 每监视器感知
    except Exception:
        pass

    root = tk.Tk()
    # 自动缩放字体和控件
    if sys.platform == 'win32':
        scaling = root.tk.call('tk', 'scaling')
        if scaling < 2.0:
            root.tk.call('tk', 'scaling', 1.5)
    app = RealCUGANGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
