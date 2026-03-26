// 图片管理器
class ImageManager {
    constructor() {
        this.uploadEndpoint = '/api/admin/images/upload';
        this.deleteEndpoint = '/api/admin/images/delete';
        this.listEndpoint = '/api/admin/images/list';
        this.cropEndpoint = '/api/admin/images/crop';
        this.maxFileSize = 10 * 1024 * 1024; // 10MB
        this.allowedTypes = ['image/jpeg', 'image/png', 'image/gif', 'image/webp'];
        this.init();
    }

    init() {
        this.setupEventListeners();
        console.log('✅ 图片管理器已初始化');
    }

    setupEventListeners() {
        // 拖拽上传
        document.addEventListener('dragover', (e) => {
            e.preventDefault();
            if (e.target.classList.contains('upload-zone')) {
                e.target.classList.add('dragover');
            }
        });

        document.addEventListener('dragleave', (e) => {
            if (e.target.classList.contains('upload-zone')) {
                e.target.classList.remove('dragover');
            }
        });

        document.addEventListener('drop', (e) => {
            e.preventDefault();
            if (e.target.classList.contains('upload-zone')) {
                e.target.classList.remove('dragover');
                const files = e.dataTransfer.files;
                if (files.length > 0) {
                    this.handleFileUpload(files[0], e.target);
                }
            }
        });
    }

    // 验证文件
    validateFile(file) {
        const errors = [];

        if (!this.allowedTypes.includes(file.type)) {
            errors.push('不支持的文件格式，请上传 JPG、PNG、GIF 或 WebP 格式的图片');
        }

        if (file.size > this.maxFileSize) {
            errors.push(`文件大小超过限制，最大允许 ${this.maxFileSize / 1024 / 1024}MB`);
        }

        return errors;
    }

    // 上传图片
    async uploadImage(file, options = {}) {
        const errors = this.validateFile(file);
        if (errors.length > 0) {
            throw new Error(errors.join('; '));
        }

        const formData = new FormData();
        formData.append('image', file);
        
        if (options.category) formData.append('category', options.category);
        if (options.destination_id) formData.append('destination_id', options.destination_id);
        if (options.description) formData.append('description', options.description);

        const response = await fetch(this.uploadEndpoint, {
            method: 'POST',
            body: formData
        });

        if (!response.ok) {
            throw new Error(`上传失败: ${response.statusText}`);
        }

        return await response.json();
    }

    // 批量上传
    async uploadMultipleImages(files, options = {}) {
        const results = [];
        const errors = [];

        for (let i = 0; i < files.length; i++) {
            try {
                const result = await this.uploadImage(files[i], options);
                results.push(result);
            } catch (error) {
                errors.push({
                    file: files[i].name,
                    error: error.message
                });
            }
        }

        return {
            success: results,
            errors: errors,
            total: files.length,
            successful: results.length,
            failed: errors.length
        };
    }

    // 删除图片
    async deleteImage(imageId) {
        const response = await fetch(this.deleteEndpoint, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ image_id: imageId })
        });

        if (!response.ok) {
            throw new Error(`删除失败: ${response.statusText}`);
        }

        return await response.json();
    }

    // 获取图片列表
    async getImageList(options = {}) {
        const params = new URLSearchParams();
        
        if (options.category) params.append('category', options.category);
        if (options.destination_id) params.append('destination_id', options.destination_id);
        if (options.page) params.append('page', options.page);
        if (options.limit) params.append('limit', options.limit);

        const url = `${this.listEndpoint}?${params.toString()}`;
        const response = await fetch(url);

        if (!response.ok) {
            throw new Error(`获取图片列表失败: ${response.statusText}`);
        }

        return await response.json();
    }

    // 裁剪图片
    async cropImage(imageId, cropData) {
        const response = await fetch(this.cropEndpoint, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                image_id: imageId,
                x: cropData.x,
                y: cropData.y,
                width: cropData.width,
                height: cropData.height
            })
        });

        if (!response.ok) {
            throw new Error(`裁剪失败: ${response.statusText}`);
        }

        return await response.json();
    }

    // 压缩图片
    compressImage(file, quality = 0.8, maxWidth = 1920, maxHeight = 1080) {
        return new Promise((resolve, reject) => {
            const canvas = document.createElement('canvas');
            const ctx = canvas.getContext('2d');
            const img = new Image();

            img.onload = () => {
                // 计算新尺寸
                let { width, height } = img;
                
                if (width > maxWidth) {
                    height = (height * maxWidth) / width;
                    width = maxWidth;
                }
                
                if (height > maxHeight) {
                    width = (width * maxHeight) / height;
                    height = maxHeight;
                }

                canvas.width = width;
                canvas.height = height;

                // 绘制压缩后的图片
                ctx.drawImage(img, 0, 0, width, height);

                canvas.toBlob((blob) => {
                    resolve(blob);
                }, file.type, quality);
            };

            img.onerror = reject;
            img.src = URL.createObjectURL(file);
        });
    }

    // 生成缩略图
    generateThumbnail(file, size = 200) {
        return new Promise((resolve, reject) => {
            const canvas = document.createElement('canvas');
            const ctx = canvas.getContext('2d');
            const img = new Image();

            img.onload = () => {
                const { width, height } = img;
                let newWidth, newHeight;

                if (width > height) {
                    newWidth = size;
                    newHeight = (height * size) / width;
                } else {
                    newHeight = size;
                    newWidth = (width * size) / height;
                }

                canvas.width = newWidth;
                canvas.height = newHeight;

                ctx.drawImage(img, 0, 0, newWidth, newHeight);

                canvas.toBlob((blob) => {
                    resolve(blob);
                }, 'image/jpeg', 0.8);
            };

            img.onerror = reject;
            img.src = URL.createObjectURL(file);
        });
    }

    // 预览图片
    previewImage(file, container) {
        const reader = new FileReader();
        reader.onload = (e) => {
            const img = document.createElement('img');
            img.src = e.target.result;
            img.className = 'preview-image img-fluid rounded';
            img.style.maxHeight = '300px';
            
            container.innerHTML = '';
            container.appendChild(img);
        };
        reader.readAsDataURL(file);
    }

    // 创建图片画廊
    createGallery(images, container) {
        container.innerHTML = '';
        container.className = 'image-gallery';

        images.forEach((image, index) => {
            const item = document.createElement('div');
            item.className = 'gallery-item';
            item.innerHTML = `
                <div class="gallery-image-wrapper">
                    <img src="${image.url}" alt="${image.name}" class="gallery-image">
                    <div class="gallery-overlay">
                        <button class="btn btn-sm btn-light me-1" onclick="imageManager.showImageDetail(${index})">
                            <i class="fas fa-eye"></i>
                        </button>
                        <button class="btn btn-sm btn-danger" onclick="imageManager.deleteImage(${image.id})">
                            <i class="fas fa-trash"></i>
                        </button>
                    </div>
                </div>
                <div class="gallery-caption">
                    <small class="text-muted">${image.name}</small>
                </div>
            `;
            container.appendChild(item);
        });
    }

    // 显示图片详情
    showImageDetail(index) {
        const modal = document.createElement('div');
        modal.className = 'modal fade';
        modal.innerHTML = `
            <div class="modal-dialog modal-lg modal-dialog-centered">
                <div class="modal-content">
                    <div class="modal-header">
                        <h5 class="modal-title">图片详情</h5>
                        <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                    </div>
                    <div class="modal-body text-center">
                        <img src="${this.currentImages[index].url}" class="img-fluid rounded">
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">关闭</button>
                        <button type="button" class="btn btn-primary" onclick="imageManager.cropImageModal(${index})">
                            <i class="fas fa-crop me-1"></i>裁剪
                        </button>
                    </div>
                </div>
            </div>
        `;

        document.body.appendChild(modal);
        const bsModal = new bootstrap.Modal(modal);
        bsModal.show();

        modal.addEventListener('hidden.bs.modal', () => {
            document.body.removeChild(modal);
        });
    }

    // 裁剪图片模态框
    cropImageModal(index) {
        const image = this.currentImages[index];
        
        const modal = document.createElement('div');
        modal.className = 'modal fade';
        modal.innerHTML = `
            <div class="modal-dialog modal-lg modal-dialog-centered">
                <div class="modal-content">
                    <div class="modal-header">
                        <h5 class="modal-title">裁剪图片</h5>
                        <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                    </div>
                    <div class="modal-body">
                        <div class="crop-container">
                            <img id="cropImage" src="${image.url}" class="img-fluid">
                        </div>
                        <div class="crop-controls mt-3">
                            <div class="row">
                                <div class="col-md-6">
                                    <label class="form-label">宽度</label>
                                    <input type="range" class="form-range" id="cropWidth" min="10" max="100" value="50">
                                </div>
                                <div class="col-md-6">
                                    <label class="form-label">高度</label>
                                    <input type="range" class="form-range" id="cropHeight" min="10" max="100" value="50">
                                </div>
                            </div>
                        </div>
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">取消</button>
                        <button type="button" class="btn btn-primary" onclick="imageManager.applyCrop()">
                            <i class="fas fa-crop me-1"></i>应用裁剪
                        </button>
                    </div>
                </div>
            </div>
        `;

        document.body.appendChild(modal);
        const bsModal = new bootstrap.Modal(modal);
        bsModal.show();

        modal.addEventListener('hidden.bs.modal', () => {
            document.body.removeChild(modal);
        });
    }

    // 应用裁剪
    applyCrop() {
        const width = document.getElementById('cropWidth').value;
        const height = document.getElementById('cropHeight').value;
        
        console.log('应用裁剪:', { width, height });
        // 这里实现实际的裁剪逻辑
    }

    // 图片滤镜
    applyFilter(imageId, filterType) {
        const filters = {
            'grayscale': 'grayscale(100%)',
            'sepia': 'sepia(100%)',
            'blur': 'blur(2px)',
            'brightness': 'brightness(120%)',
            'contrast': 'contrast(120%)',
            'saturate': 'saturate(150%)'
        };

        const img = document.querySelector(`[data-image-id="${imageId}"]`);
        if (img && filters[filterType]) {
            img.style.filter = filters[filterType];
        }
    }

    // 批量操作
    async batchOperation(operation, imageIds) {
        const results = [];

        for (const imageId of imageIds) {
            try {
                let result;
                switch (operation) {
                    case 'delete':
                        result = await this.deleteImage(imageId);
                        break;
                    case 'crop':
                        result = await this.cropImage(imageId, { x: 0, y: 0, width: 100, height: 100 });
                        break;
                    default:
                        throw new Error('未知操作');
                }
                results.push({ id: imageId, success: true, result });
            } catch (error) {
                results.push({ id: imageId, success: false, error: error.message });
            }
        }

        return results;
    }

    // 获取图片信息
    getImageInfo(file) {
        return new Promise((resolve, reject) => {
            const img = new Image();
            img.onload = () => {
                resolve({
                    width: img.width,
                    height: img.height,
                    size: file.size,
                    type: file.type,
                    name: file.name,
                    lastModified: file.lastModified
                });
            };
            img.onerror = reject;
            img.src = URL.createObjectURL(file);
        });
    }

    // 检查图片完整性
    checkImageIntegrity(file) {
        return new Promise((resolve) => {
            const img = new Image();
            img.onload = () => resolve(true);
            img.onerror = () => resolve(false);
            img.src = URL.createObjectURL(file);
        });
    }
}

// 创建全局实例
const imageManager = new ImageManager();

// 导出模块
if (typeof module !== 'undefined' && module.exports) {
    module.exports = ImageManager;
}

// 暴露到全局
window.ImageManager = ImageManager;
window.imageManager = imageManager;