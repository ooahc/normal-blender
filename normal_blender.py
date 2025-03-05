import sys
import os
import json
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                            QHBoxLayout, QLabel, QPushButton, QFileDialog, 
                            QSpinBox, QDoubleSpinBox, QListWidget, QMessageBox,
                            QTreeWidget, QTreeWidgetItem, QTableWidget, 
                            QTableWidgetItem, QComboBox)
from PyQt6.QtCore import Qt
import cv2
import numpy as np
from PIL import Image

class BlendTask:
    def __init__(self, name):
        self.name = name
        self.items = []  # 存储BlendItem对象
        self.enabled = True

class BlendItem:
    def __init__(self, name, path):
        self.name = name
        self.path = path
        self.weight = 1.0
        self.blend_mode = "Normal"  # 混合模式
        self.enabled = True

class NormalMapBlender(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("法线贴图混合工具")
        self.setMinimumSize(1200, 800)
        
        # 数据存储
        self.tasks = []  # 存储BlendTask对象
        self.output_dir = ""
        
        self.init_ui()
    
    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        
        # 左侧面板 - 任务树
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        
        # 任务树
        self.task_tree = QTreeWidget()
        self.task_tree.setHeaderLabels(["混合任务"])
        left_layout.addWidget(QLabel("任务列表："))
        left_layout.addWidget(self.task_tree)
        
        # 任务控制按钮
        task_btn_layout = QHBoxLayout()
        btn_add_task = QPushButton("添加任务")
        btn_add_task.clicked.connect(self.add_task)
        btn_remove_task = QPushButton("删除任务")
        btn_remove_task.clicked.connect(self.remove_task)
        task_btn_layout.addWidget(btn_add_task)
        task_btn_layout.addWidget(btn_remove_task)
        left_layout.addLayout(task_btn_layout)
        
        # 子项控制按钮
        item_btn_layout = QHBoxLayout()
        btn_add_item = QPushButton("添加子项")
        btn_add_item.clicked.connect(self.add_item)
        btn_remove_item = QPushButton("删除子项")
        btn_remove_item.clicked.connect(self.remove_item)
        item_btn_layout.addWidget(btn_add_item)
        item_btn_layout.addWidget(btn_remove_item)
        left_layout.addLayout(item_btn_layout)
        
        main_layout.addWidget(left_panel)
        
        # 中间面板 - 参数表格
        middle_panel = QWidget()
        middle_layout = QVBoxLayout(middle_panel)
        
        # 参数表格
        self.param_table = QTableWidget()
        self.param_table.setColumnCount(4)
        self.param_table.setHorizontalHeaderLabels(["名称", "权重", "混合模式", "启用"])
        middle_layout.addWidget(QLabel("参数设置："))
        middle_layout.addWidget(self.param_table)
        
        main_layout.addWidget(middle_panel)
        
        # 右侧面板 - 预览和控制
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        
        # 预览区域
        right_layout.addWidget(QLabel("预览："))
        self.preview_label = QLabel()
        self.preview_label.setMinimumSize(400, 400)
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        right_layout.addWidget(self.preview_label)
        
        # 预览控制
        preview_controls = QHBoxLayout()
        btn_reset = QPushButton("重置")
        btn_reset.clicked.connect(self.reset_preview)
        btn_update = QPushButton("更新预览")
        btn_update.clicked.connect(self.update_preview)
        preview_controls.addWidget(btn_reset)
        preview_controls.addWidget(btn_update)
        right_layout.addLayout(preview_controls)
        
        # 输出控制
        output_controls = QVBoxLayout()
        btn_output = QPushButton("选择输出目录")
        btn_output.clicked.connect(self.select_output_dir)
        btn_blend = QPushButton("开始混合")
        btn_blend.clicked.connect(self.blend_normal_maps)
        output_controls.addWidget(btn_output)
        output_controls.addWidget(btn_blend)
        right_layout.addLayout(output_controls)
        
        main_layout.addWidget(right_panel)
    
    def add_task(self):
        task_name = f"blende-task-{len(self.tasks) + 1}"
        task = BlendTask(task_name)
        self.tasks.append(task)
        
        task_item = QTreeWidgetItem(self.task_tree)
        task_item.setText(0, task_name)
        self.task_tree.addTopLevelItem(task_item)
    
    def add_item(self):
        current_task = self.get_selected_task()
        if not current_task:
            QMessageBox.warning(self, "警告", "请先选择一个任务")
            return
            
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "选择法线贴图",
            "",
            "图像文件 (*.png *.jpg *.jpeg)"
        )
        
        if not files:  # 如果用户取消选择，直接返回
            return
        
        current_tree_item = self.task_tree.currentItem()
        # 如果当前选中的是子项，获取其父项
        if current_tree_item.parent():
            current_tree_item = current_tree_item.parent()
        
        for file in files:
            item_name = f"blende-item-{len(current_task.items) + 1}"
            blend_item = BlendItem(item_name, file)
            current_task.items.append(blend_item)
            
            # 创建新的树项目
            item = QTreeWidgetItem(current_tree_item)
            item.setText(0, f"{item_name} ({os.path.basename(file)})")
        
        self.update_param_table()
    
    def remove_task(self):
        current_row = self.task_tree.currentRow()
        if current_row >= 0:
            self.task_tree.takeTopLevelItem(current_row)
            self.tasks.pop(current_row)
    
    def remove_item(self):
        """删除选中的任务或子项"""
        current_item = self.task_tree.currentItem()
        if not current_item:
            QMessageBox.warning(self, "警告", "请先选择要删除的项目")
            return
        
        # 获取父项（如果是子项的话）
        parent_item = current_item.parent()
        
        if parent_item:  # 如果是子项
            # 找到对应的任务
            task_index = self.task_tree.indexOfTopLevelItem(parent_item)
            if task_index >= 0 and task_index < len(self.tasks):
                task = self.tasks[task_index]
                # 获取子项在父项中的索引
                item_index = parent_item.indexOfChild(current_item)
                if item_index >= 0 and item_index < len(task.items):
                    # 从数据模型中移除
                    task.items.pop(item_index)
                    # 从树中移除
                    parent_item.removeChild(current_item)
        else:  # 如果是任务项
            task_index = self.task_tree.indexOfTopLevelItem(current_item)
            if task_index >= 0:
                # 从数据模型中移除
                self.tasks.pop(task_index)
                # 从树中移除
                self.task_tree.takeTopLevelItem(task_index)
        
        # 更新参数表格
        self.update_param_table()

    def select_output_dir(self):
        dir_path = QFileDialog.getExistingDirectory(
            self,
            "选择输出目录",
            ""
        )
        if dir_path:
            self.output_dir = dir_path
    
    def blend_normal_maps(self):
        if len(self.tasks) < 1:
            QMessageBox.warning(self, "警告", "请至少添加一个任务")
            return
            
        if not self.output_dir:
            QMessageBox.warning(self, "警告", "请选择输出目录")
            return
        
        try:
            # 读取第一张图确定尺寸
            first_map = cv2.imread(self.tasks[0].items[0].path)
            height, width = first_map.shape[:2]
            
            # 初始化结果数组
            result = np.zeros_like(first_map, dtype=np.float32)
            total_weight = 0
            
            # 混合所有法线贴图
            for task in self.tasks:
                for item in task.items:
                    img = cv2.imread(item.path)
                    if img.shape[:2] != (height, width):
                        img = cv2.resize(img, (width, height))
                    
                    weight = item.weight
                    result += img.astype(np.float32) * weight
                    total_weight += weight
            
            # 归一化
            if total_weight > 0:
                result /= total_weight
            
            # 保存结果
            output_path = os.path.join(self.output_dir, "blended_normal.png")
            cv2.imwrite(output_path, result.astype(np.uint8))
            
            QMessageBox.information(self, "成功", f"混合完成！\n保存至：{output_path}")
            
        except Exception as e:
            QMessageBox.critical(self, "错误", f"处理过程中出现错误：{str(e)}")

    def get_selected_task(self):
        """获取当前选中的任务"""
        current_item = self.task_tree.currentItem()
        if not current_item:
            return None
        
        # 如果选中的是子项，获取其父任务项
        parent = current_item.parent()
        task_item = parent if parent else current_item
        
        # 获取任务索引
        task_index = self.task_tree.indexOfTopLevelItem(task_item)
        if task_index >= 0 and task_index < len(self.tasks):
            return self.tasks[task_index]
        
        return None

    def update_param_table(self):
        """更新参数表格"""
        self.param_table.setRowCount(0)  # 清空表格
        
        current_task = self.get_selected_task()
        if not current_task:
            return
        
        # 更新表格内容
        for index, item in enumerate(current_task.items):
            self.param_table.insertRow(index)
            
            # 名称
            name_item = QTableWidgetItem(item.name)
            self.param_table.setItem(index, 0, name_item)
            
            # 权重
            weight_spin = QDoubleSpinBox()
            weight_spin.setRange(0, 1)
            weight_spin.setSingleStep(0.1)
            weight_spin.setValue(item.weight)
            weight_spin.valueChanged.connect(lambda value, row=index: self.update_item_weight(row, value))
            self.param_table.setCellWidget(index, 1, weight_spin)
            
            # 混合模式
            blend_mode_combo = QComboBox()
            blend_modes = ["Normal", "Multiply", "Add", "Overlay"]  # 可以添加更多混合模式
            blend_mode_combo.addItems(blend_modes)
            blend_mode_combo.setCurrentText(item.blend_mode)
            blend_mode_combo.currentTextChanged.connect(lambda text, row=index: self.update_item_blend_mode(row, text))
            self.param_table.setCellWidget(index, 2, blend_mode_combo)
            
            # 启用状态
            enabled_item = QTableWidgetItem()
            enabled_item.setCheckState(Qt.CheckState.Checked if item.enabled else Qt.CheckState.Unchecked)
            self.param_table.setItem(index, 3, enabled_item)
        
        self.param_table.resizeColumnsToContents()

    def update_item_weight(self, row, value):
        """更新子项权重"""
        current_task = self.get_selected_task()
        if current_task and row < len(current_task.items):
            current_task.items[row].weight = value
            self.update_preview()

    def update_item_blend_mode(self, row, mode):
        """更新子项混合模式"""
        current_task = self.get_selected_task()
        if current_task and row < len(current_task.items):
            current_task.items[row].blend_mode = mode
            self.update_preview()

    def reset_preview(self):
        self.preview_label.setPixmap(QPixmap())

    def update_preview(self):
        current_task = self.get_selected_task()
        if not current_task or not current_task.items:
            self.preview_label.setPixmap(QPixmap())
            return
        
        img = cv2.imread(current_task.items[0].path)
        self.preview_label.setPixmap(QPixmap.fromImage(QImage(img.data, img.shape[1], img.shape[0], QImage.Format.Format_RGB888).scaled(400, 400)))

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = NormalMapBlender()
    window.show()
    sys.exit(app.exec())