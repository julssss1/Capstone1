// Admin Lesson Add/Edit JavaScript
let itemCounter = 0;

// Load existing content if editing
function initializeLessonItems(existingContent) {
    if (Array.isArray(existingContent)) {
        existingContent.forEach((item) => {
            addLessonItem(item);
        });
    }
}

function addLessonItem(existingData = null) {
    itemCounter++;
    const itemId = `item-${itemCounter}`;
    
    const itemDiv = document.createElement('div');
    itemDiv.className = 'lesson-item';
    itemDiv.id = itemId;
    
    const name = existingData?.name || '';
    const description = existingData?.description || '';
    const imageFilename = existingData?.image_filename || '';
    const videoUrl = existingData?.video_url || '';
    const mediaUrl = existingData?.media_url || existingData?.image_url || '';
    
    // Determine preview HTML
    let previewHtml = '';
    if (mediaUrl) {
        if (videoUrl || existingData?.video_url) {
            previewHtml = `<video controls src="${mediaUrl}"></video>`;
        } else {
            previewHtml = `<img src="${mediaUrl}" alt="Preview">`;
        }
    } else if (imageFilename) {
        previewHtml = `<img src="/static/Images/${imageFilename}" alt="Preview">`;
    }
    
    itemDiv.innerHTML = `
        <div class="lesson-item-header">
            <h4>Lesson Item ${itemCounter}</h4>
            <button type="button" class="remove-item-btn" onclick="removeLessonItem('${itemId}')">
                <i class="fas fa-trash"></i> Remove
            </button>
        </div>
        
        <div class="form-row">
            <div class="form-group">
                <label>Item Title (e.g., "Letter A")</label>
                <input type="text" class="item-name" value="${name}" placeholder="Enter item title">
            </div>
            <div class="form-group">
                <label>Description</label>
                <input type="text" class="item-description" value="${description}" placeholder="Enter description">
            </div>
        </div>
        
        <div class="form-group">
            <label>Upload Image</label>
            <div class="file-input-wrapper">
                <label for="image-${itemId}" class="file-input-label">
                    <i class="fas fa-image"></i> Choose Image
                </label>
                <input type="file" id="image-${itemId}" class="item-image-file" accept="image/*" onchange="handleImageUpload(this, '${itemId}')">
                <span class="image-file-name" style="margin-left: 10px; font-size: 14px;">No file chosen</span>
            </div>
            <div class="image-upload-status" style="display: none;">Uploading...</div>
            <div class="image-upload-error" style="display: none;"></div>
            <input type="hidden" class="item-image-url" value="${mediaUrl || imageFilename || existingData?.image_url || ''}">
            <div class="image-preview">
                ${(mediaUrl && !videoUrl) || imageFilename || existingData?.image_url ? `<img src="${existingData?.image_url || mediaUrl || '/static/Images/' + imageFilename}" alt="Preview">` : ''}
            </div>
        </div>
        
        <div class="form-group">
            <label>Upload Video (Optional)</label>
            <div class="file-input-wrapper">
                <label for="video-${itemId}" class="file-input-label">
                    <i class="fas fa-video"></i> Choose Video
                </label>
                <input type="file" id="video-${itemId}" class="item-video-file" accept="video/*" onchange="handleVideoUpload(this, '${itemId}')">
                <span class="video-file-name" style="margin-left: 10px; font-size: 14px;">No file chosen</span>
            </div>
            <div class="video-upload-status" style="display: none;">Uploading...</div>
            <div class="video-upload-error" style="display: none;"></div>
            <input type="hidden" class="item-video-url" value="${videoUrl || existingData?.video_url || ''}">
            <div class="video-preview">
                ${videoUrl || existingData?.video_url ? `<video controls src="${videoUrl || existingData?.video_url}"></video>` : ''}
            </div>
        </div>
    `;
    
    document.getElementById('lessonItemsContainer').appendChild(itemDiv);
}

function removeLessonItem(itemId) {
    const item = document.getElementById(itemId);
    if (item) {
        item.remove();
    }
}

async function handleImageUpload(input, itemId) {
    const file = input.files[0];
    if (!file) return;
    
    const itemDiv = document.getElementById(itemId);
    const statusDiv = itemDiv.querySelector('.image-upload-status');
    const errorDiv = itemDiv.querySelector('.image-upload-error');
    const previewDiv = itemDiv.querySelector('.image-preview');
    const fileNameSpan = itemDiv.querySelector('.image-file-name');
    const imageUrlInput = itemDiv.querySelector('.item-image-url');
    
    fileNameSpan.textContent = file.name;
    statusDiv.style.display = 'block';
    errorDiv.style.display = 'none';
    
    const formData = new FormData();
    formData.append('file', file);
    
    try {
        const response = await fetch('/admin/lesson/upload-media', {
            method: 'POST',
            body: formData
        });
        
        const result = await response.json();
        
        if (result.success) {
            statusDiv.textContent = 'Upload successful!';
            imageUrlInput.value = result.url;
            previewDiv.innerHTML = `<img src="${result.url}" alt="Preview">`;
            
            setTimeout(() => {
                statusDiv.style.display = 'none';
            }, 3000);
        } else {
            throw new Error(result.error || 'Upload failed');
        }
    } catch (error) {
        errorDiv.textContent = `Error: ${error.message}`;
        errorDiv.style.display = 'block';
        statusDiv.style.display = 'none';
    }
}

async function handleVideoUpload(input, itemId) {
    const file = input.files[0];
    if (!file) return;
    
    const itemDiv = document.getElementById(itemId);
    const statusDiv = itemDiv.querySelector('.video-upload-status');
    const errorDiv = itemDiv.querySelector('.video-upload-error');
    const previewDiv = itemDiv.querySelector('.video-preview');
    const fileNameSpan = itemDiv.querySelector('.video-file-name');
    const videoUrlInput = itemDiv.querySelector('.item-video-url');
    
    fileNameSpan.textContent = file.name;
    statusDiv.style.display = 'block';
    errorDiv.style.display = 'none';
    
    const formData = new FormData();
    formData.append('file', file);
    
    try {
        const response = await fetch('/admin/lesson/upload-media', {
            method: 'POST',
            body: formData
        });
        
        const result = await response.json();
        
        if (result.success) {
            statusDiv.textContent = 'Upload successful!';
            videoUrlInput.value = result.url;
            previewDiv.innerHTML = `<video controls src="${result.url}"></video>`;
            
            setTimeout(() => {
                statusDiv.style.display = 'none';
            }, 3000);
        } else {
            throw new Error(result.error || 'Upload failed');
        }
    } catch (error) {
        errorDiv.textContent = `Error: ${error.message}`;
        errorDiv.style.display = 'block';
        statusDiv.style.display = 'none';
    }
}

// Handle form submission
function initializeLessonForm() {
    const form = document.getElementById('lessonForm');
    if (!form) return;
    
    form.addEventListener('submit', function(e) {
        e.preventDefault();
        
        const items = [];
        const itemDivs = document.querySelectorAll('.lesson-item');
        
        itemDivs.forEach(itemDiv => {
            const name = itemDiv.querySelector('.item-name').value.trim();
            const description = itemDiv.querySelector('.item-description').value.trim();
            const imageUrl = itemDiv.querySelector('.item-image-url').value.trim();
            const videoUrl = itemDiv.querySelector('.item-video-url').value.trim();
            
            if (name) {
                const item = {
                    name: name,
                    description: description
                };
                
                // Handle image
                if (imageUrl) {
                    if (imageUrl.startsWith('http')) {
                        // New uploaded image from Supabase Storage
                        item.image_url = imageUrl;
                    } else {
                        // Existing static file
                        item.image_filename = imageUrl;
                    }
                }
                
                // Handle video
                if (videoUrl) {
                    item.video_url = videoUrl;
                }
                
                items.push(item);
            }
        });
        
        // Set the JSON content
        document.getElementById('content_json').value = JSON.stringify(items);
        
        // Submit the form
        this.submit();
    });
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
    initializeLessonForm();
    
    // Load existing content if editing (passed from template)
    if (window.existingLessonContent) {
        initializeLessonItems(window.existingLessonContent);
    }
});
