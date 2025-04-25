document.addEventListener('DOMContentLoaded', function() {
    // 初始化文件上传功能
    initFileUpload();
    
    // 初始化表单验证
    initFormValidation();
    
    // 初始化登录/注册标签切换
    initAuthTabs();
    
    // 初始化通知消息自动关闭
    initAlertDismiss();
    
    // 初始化模态对话框
    initModals();
    
    // 初始化删除确认功能
    initDeleteConfirmation();
    
    // 初始化描述单元格的tooltip功能
    initDescriptionTooltips();
    
    // 文件上传控件交互
    const fileInputs = document.querySelectorAll('.custom-file-input');
    if (fileInputs.length > 0) {
        fileInputs.forEach(input => {
            // 当选择文件后，显示文件名
            input.addEventListener('change', function(e) {
                const fileName = e.target.files[0] ? e.target.files[0].name : '选择文件...';
                const label = e.target.nextElementSibling;
                if (label) {
                    label.textContent = fileName;
                }
            });
        });
    }
    
    // 添加学生切换显示
    const showAddStudentBtn = document.getElementById('showAddStudentBtn');
    const addStudentSection = document.getElementById('addStudentSection');
    
    if (showAddStudentBtn && addStudentSection) {
        showAddStudentBtn.addEventListener('click', function() {
            const isVisible = addStudentSection.style.display !== 'none';
            addStudentSection.style.display = isVisible ? 'none' : 'block';
            showAddStudentBtn.innerHTML = isVisible ? 
                '<i class="fas fa-user-plus"></i> 添加学生' : 
                '<i class="fas fa-times"></i> 取消添加';
        });
    }
    
    // 单个添加/批量导入切换
    const addTabButtons = document.querySelectorAll('[data-target]');
    const addMethods = document.querySelectorAll('.add-method');
    
    if (addTabButtons.length > 0 && addMethods.length > 0) {
        addTabButtons.forEach(button => {
            button.addEventListener('click', function() {
                // 移除所有活动状态
                addTabButtons.forEach(btn => {
                    btn.classList.remove('active');
                    btn.classList.remove('btn-primary');
                    btn.classList.add('btn-outline-primary');
                });
                
                // 隐藏所有添加方式
                addMethods.forEach(method => {
                    method.classList.remove('active');
                    method.style.display = 'none';
                });
                
                // 显示选中的添加方式
                const targetId = this.getAttribute('data-target');
                const targetMethod = document.getElementById(targetId);
                if (targetMethod) {
                    targetMethod.classList.add('active');
                    targetMethod.style.display = 'block';
                }
                
                // 激活当前按钮
                this.classList.add('active');
                this.classList.add('btn-primary');
                this.classList.remove('btn-outline-primary');
            });
        });
    }
    
    // 多选框样式
    const checkboxes = document.querySelectorAll('.custom-checkbox .custom-control-input');
    if (checkboxes.length > 0) {
        checkboxes.forEach(checkbox => {
            // 为每个复选框添加事件监听
            checkbox.addEventListener('change', function() {
                const label = this.nextElementSibling;
                if (label) {
                    if (this.checked) {
                        label.classList.add('checked');
                    } else {
                        label.classList.remove('checked');
                    }
                }
            });
        });
    }
});

// 文件上传功能
function initFileUpload() {
    const fileUploads = document.querySelectorAll('.file-upload');
    
    fileUploads.forEach(upload => {
        const input = upload.querySelector('input[type="file"]');
        const fileList = upload.nextElementSibling;
        
        if (input && fileList) {
            input.addEventListener('change', function(e) {
                // 清空之前的文件列表
                while (fileList.firstChild) {
                    fileList.removeChild(fileList.firstChild);
                }
                
                // 显示新选择的文件
                for (let i = 0; i < this.files.length; i++) {
                    const file = this.files[i];
                    const fileItem = document.createElement('div');
                    fileItem.className = 'file-item';
                    
                    // 确定文件图标
                    let iconClass = 'fa-file';
                    if (file.type.startsWith('image/')) {
                        iconClass = 'fa-file-image';
                    } else if (file.type.startsWith('video/')) {
                        iconClass = 'fa-file-video';
                    } else if (file.type.startsWith('audio/')) {
                        iconClass = 'fa-file-audio';
                    } else if (file.type === 'application/pdf') {
                        iconClass = 'fa-file-pdf';
                    } else if (file.type.includes('word')) {
                        iconClass = 'fa-file-word';
                    } else if (file.type.includes('excel') || file.type.includes('sheet')) {
                        iconClass = 'fa-file-excel';
                    } else if (file.type.includes('powerpoint') || file.type.includes('presentation')) {
                        iconClass = 'fa-file-powerpoint';
                    }
                    
                    // 格式化文件大小
                    const fileSize = formatFileSize(file.size);
                    
                    fileItem.innerHTML = `
                        <div>
                            <i class="fas ${iconClass}"></i>
                            <span>${file.name}</span>
                        </div>
                        <div>
                            <span class="file-size">${fileSize}</span>
                            <button type="button" class="btn-remove"><i class="fas fa-times"></i></button>
                        </div>
                    `;
                    
                    // 添加删除按钮事件
                    const removeBtn = fileItem.querySelector('.btn-remove');
                    removeBtn.addEventListener('click', function() {
                        fileItem.remove();
                        // 注意：这只删除UI上的文件项，实际的文件上传需要在提交表单时处理
                    });
                    
                    fileList.appendChild(fileItem);
                }
            });
            
            // 拖放功能
            upload.addEventListener('dragover', function(e) {
                e.preventDefault();
                upload.classList.add('dragover');
            });
            
            upload.addEventListener('dragleave', function() {
                upload.classList.remove('dragover');
            });
            
            upload.addEventListener('drop', function(e) {
                e.preventDefault();
                upload.classList.remove('dragover');
                
                if (e.dataTransfer.files.length) {
                    input.files = e.dataTransfer.files;
                    // 触发change事件以显示文件
                    const event = new Event('change', { bubbles: true });
                    input.dispatchEvent(event);
                }
            });
        }
    });
}

// 格式化文件大小
function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

// 表单验证
function initFormValidation() {
    const forms = document.querySelectorAll('form.needs-validation');
    
    forms.forEach(form => {
        form.addEventListener('submit', function(event) {
            if (!form.checkValidity()) {
                event.preventDefault();
                event.stopPropagation();
            }
            
            form.classList.add('was-validated');
        }, false);
    });
}

// 登录/注册标签切换
function initAuthTabs() {
    const authTabs = document.querySelectorAll('.auth-tab');
    const authForms = document.querySelectorAll('.auth-form');
    
    authTabs.forEach(tab => {
        tab.addEventListener('click', function() {
            // 移除所有选项卡的活动状态
            authTabs.forEach(t => t.classList.remove('active'));
            // 隐藏所有表单
            authForms.forEach(f => f.style.display = 'none');
            
            // 激活当前选项卡
            this.classList.add('active');
            
            // 显示对应的表单
            const targetForm = document.getElementById(this.dataset.target);
            if (targetForm) {
                targetForm.style.display = 'block';
            }
        });
    });
}

// 警告消息自动关闭
function initAlertDismiss() {
    const alerts = document.querySelectorAll('.alert');
    
    alerts.forEach(alert => {
        // 添加关闭按钮
        const closeBtn = document.createElement('button');
        closeBtn.className = 'close-alert';
        closeBtn.innerHTML = '&times;';
        closeBtn.addEventListener('click', function() {
            alert.style.display = 'none';
        });
        
        alert.appendChild(closeBtn);
        
        // 5秒后自动关闭
        setTimeout(() => {
            alert.style.opacity = '0';
            setTimeout(() => {
                alert.style.display = 'none';
            }, 300);
        }, 5000);
    });
}

// 表格排序功能
function initTableSort() {
    const tables = document.querySelectorAll('.sortable');
    
    tables.forEach(table => {
        const headers = table.querySelectorAll('th');
        
        headers.forEach((header, index) => {
            if (header.classList.contains('sortable')) {
                header.addEventListener('click', function() {
                    sortTable(table, index);
                });
                
                // 添加排序图标
                header.innerHTML += ' <i class="fas fa-sort"></i>';
            }
        });
    });
}

function sortTable(table, columnIndex) {
    const tbody = table.querySelector('tbody');
    const rows = Array.from(tbody.querySelectorAll('tr'));
    const header = table.querySelectorAll('th')[columnIndex];
    
    // 确定排序方向
    const isAscending = header.classList.contains('sort-asc');
    
    // 清除所有排序指示器
    table.querySelectorAll('th').forEach(th => {
        th.classList.remove('sort-asc', 'sort-desc');
        const icon = th.querySelector('i');
        if (icon) icon.className = 'fas fa-sort';
    });
    
    // 设置新的排序方向
    if (isAscending) {
        header.classList.add('sort-desc');
        header.querySelector('i').className = 'fas fa-sort-down';
    } else {
        header.classList.add('sort-asc');
        header.querySelector('i').className = 'fas fa-sort-up';
    }
    
    // 排序行
    rows.sort((a, b) => {
        const aValue = a.cells[columnIndex].textContent.trim();
        const bValue = b.cells[columnIndex].textContent.trim();
        
        // 判断是否为数字
        if (!isNaN(aValue) && !isNaN(bValue)) {
            return isAscending ? bValue - aValue : aValue - bValue;
        } else {
            return isAscending 
                ? bValue.localeCompare(aValue) 
                : aValue.localeCompare(bValue);
        }
    });
    
    // 重新添加排序后的行
    rows.forEach(row => tbody.appendChild(row));
}

// 模态对话框功能
function initModals() {
    // 关闭模态框的事件处理
    document.addEventListener('click', function(e) {
        if (e.target.classList.contains('modal-overlay') || 
            e.target.classList.contains('modal-close') || 
            e.target.classList.contains('btn-cancel')) {
            closeModal(e.target.closest('.modal-overlay'));
        }
    });
}

// 打开模态框
function openModal(modalId, options = {}) {
    // 创建模态框覆盖层
    const overlay = document.createElement('div');
    overlay.className = 'modal-overlay';
    overlay.id = `overlay-${modalId}`;
    
    // 创建模态框
    const modal = document.createElement('div');
    modal.className = 'modal';
    
    // 创建模态框标题
    const header = document.createElement('div');
    header.className = 'modal-header';
    
    const title = document.createElement('h3');
    title.textContent = options.title || '提示';
    header.appendChild(title);
    
    const closeButton = document.createElement('button');
    closeButton.className = 'modal-close';
    closeButton.innerHTML = '&times;';
    header.appendChild(closeButton);
    
    // 创建模态框内容
    const body = document.createElement('div');
    body.className = 'modal-body';
    body.innerHTML = options.content || '';
    
    // 创建模态框按钮
    const footer = document.createElement('div');
    footer.className = 'modal-footer';
    
    if (options.cancelText) {
        const cancelButton = document.createElement('button');
        cancelButton.className = 'btn btn-secondary btn-cancel';
        cancelButton.textContent = options.cancelText;
        cancelButton.onclick = options.onCancel || function() { closeModal(overlay); };
        footer.appendChild(cancelButton);
    }
    
    if (options.confirmText) {
        const confirmButton = document.createElement('button');
        confirmButton.className = `btn ${options.confirmButtonClass || 'btn-primary'} btn-confirm`;
        confirmButton.textContent = options.confirmText;
        confirmButton.onclick = options.onConfirm || function() { closeModal(overlay); };
        footer.appendChild(confirmButton);
    }
    
    // 组装模态框
    modal.appendChild(header);
    modal.appendChild(body);
    modal.appendChild(footer);
    overlay.appendChild(modal);
    
    // 添加到文档中
    document.body.appendChild(overlay);
    
    // 显示模态框
    setTimeout(() => {
        overlay.style.opacity = 1;
    }, 10);
    
    return overlay;
}

// 关闭模态框
function closeModal(overlay) {
    if (!overlay) return;
    
    overlay.style.opacity = 0;
    setTimeout(() => {
        if (overlay.parentNode) {
            overlay.parentNode.removeChild(overlay);
        }
    }, 300);
}

// 删除确认功能
function initDeleteConfirmation() {
    // 查找所有带有data-confirm属性的元素
    const deleteButtons = document.querySelectorAll('[data-confirm]');
    
    deleteButtons.forEach(button => {
        button.addEventListener('click', function(e) {
            e.preventDefault();
            
            const message = this.getAttribute('data-confirm') || '确定要删除此项吗？';
            const url = this.getAttribute('href') || this.getAttribute('data-url');
            
            // 打开删除确认对话框
            openModal('delete-confirm', {
                title: '确认删除',
                content: `<p>${message}</p><p class="text-muted">此操作不可逆，请慎重操作。</p>`,
                confirmText: '删除',
                confirmButtonClass: 'btn-danger',
                cancelText: '取消',
                onConfirm: function() {
                    if (url) {
                        window.location.href = url;
                    } else if (button.form) {
                        button.form.submit();
                    }
                }
            });
        });
    });
}

// 为描述单元格添加悬停显示完整内容的功能
function initDescriptionTooltips() {
    console.log("初始化描述气泡功能");
    const descriptionCells = document.querySelectorAll('.description-cell');
    console.log("找到描述单元格:", descriptionCells.length);
    
    // 创建一个全局的tooltip元素
    let tooltip = document.querySelector('.description-tooltip');
    if (!tooltip) {
        tooltip = document.createElement('div');
        tooltip.className = 'description-tooltip';
        document.body.appendChild(tooltip);
    }
    
    descriptionCells.forEach((cell, index) => {
        const fullText = cell.getAttribute('data-description');
        
        // 鼠标进入显示tooltip
        cell.addEventListener('mouseenter', function(e) {
            // 检查文本是否被截断
            const isTruncated = this.offsetWidth < this.scrollWidth;
            console.log(`单元格 ${index + 1} 是否截断:`, isTruncated, 
                      `(offsetWidth: ${this.offsetWidth}, scrollWidth: ${this.scrollWidth})`);
            
            if (isTruncated) {
                tooltip.textContent = fullText;
                
                // 获取单元格的位置
                const rect = this.getBoundingClientRect();
                
                // 设置tooltip位置 - 相对于视口
                tooltip.style.left = rect.left + 'px';
                tooltip.style.top = (rect.bottom + 5) + 'px'; // 5px 间距
                
                // 检查右侧是否有足够空间，如果没有则左对齐
                const tooltipWidth = Math.min(400, Math.max(200, rect.width));
                if (rect.left + tooltipWidth > window.innerWidth) {
                    tooltip.style.left = (window.innerWidth - tooltipWidth - 10) + 'px';
                }
                
                tooltip.style.display = 'block';
                console.log(`显示气泡在位置: 左 ${tooltip.style.left}, 上 ${tooltip.style.top}`);
            }
        });
        
        // 鼠标离开隐藏tooltip
        cell.addEventListener('mouseleave', function() {
            tooltip.style.display = 'none';
        });
    });
    
    // 确保滚动时气泡隐藏
    window.addEventListener('scroll', function() {
        tooltip.style.display = 'none';
    });
}

// 简化检测文本截断的方法
function isTextTruncated(element) {
    return element.offsetWidth < element.scrollWidth;
} 