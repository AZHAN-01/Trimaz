// Trimaz - Frontend Application
document.addEventListener("DOMContentLoaded", () => {
    // State
    let currentUploadedFile = null;
    let currentTaskId = null;
    let pollInterval = null;
    let currentDuration = 60; // Default 1 minute (60s)

    // DOM Elements
    const dropzone = document.getElementById("dropzone");
    const videoInput = document.getElementById("videoInput");
    
    // Sections
    const uploadSection = document.getElementById("uploadSection");
    const configSection = document.getElementById("configSection");
    const processingSection = document.getElementById("processingSection");
    const resultsSection = document.getElementById("resultsSection");
    
    // Upload Progress
    const uploadProgressContainer = document.getElementById("uploadProgressContainer");
    const uploadProgressBar = document.getElementById("uploadProgressBar");
    const uploadProgressPercent = document.getElementById("uploadProgressPercent");
    const uploadProgressLabel = document.getElementById("uploadProgressLabel");
    const uploadStats = document.getElementById("uploadStats");

    // Video Meta Elements
    const videoThumb = document.getElementById("videoThumb");
    const videoFilename = document.getElementById("videoFilename");
    const metaDuration = document.getElementById("metaDuration");
    const metaResolution = document.getElementById("metaResolution");
    const metaFps = document.getElementById("metaFps");
    const metaSize = document.getElementById("metaSize");
    const reelsEstimateText = document.getElementById("reelsEstimateText");

    // Controls
    const presetButtons = document.querySelectorAll(".preset-btn");
    const customDuration = document.getElementById("customDuration");
    const modeCards = document.querySelectorAll(".mode-card");
    const overlapSelect = document.getElementById("overlapSelect");
    const prefixInput = document.getElementById("prefixInput");
    const startProcessBtn = document.getElementById("startProcessBtn");
    const cancelConfigBtn = document.getElementById("cancelConfigBtn");
    const startNewVideoBtn = document.getElementById("startNewVideoBtn");

    // Processing Elements
    const taskProgressBar = document.getElementById("taskProgressBar");
    const processingTitle = document.getElementById("processingTitle");
    const processingSubtitle = document.getElementById("processingSubtitle");
    const taskClipCount = document.getElementById("taskClipCount");
    const taskPercent = document.getElementById("taskPercent");

    // Results Elements
    const resultsHeaderTitle = document.getElementById("resultsHeaderTitle");
    const resultsHeaderSubtitle = document.getElementById("resultsHeaderSubtitle");
    const reelsGrid = document.getElementById("reelsGrid");
    const downloadAllBtn = document.getElementById("downloadAllBtn");
    const openFolderBtn = document.getElementById("openFolderBtn");

    // Modal Elements
    const videoModal = document.getElementById("videoModal");
    const modalBackdrop = document.getElementById("modalBackdrop");
    const modalCloseBtn = document.getElementById("modalCloseBtn");
    const modalVideoPlayer = document.getElementById("modalVideoPlayer");
    const modalVideoTitle = document.getElementById("modalVideoTitle");
    const modalDownloadBtn = document.getElementById("modalDownloadBtn");

    // Toast
    const toast = document.getElementById("toast");

    // ----------------------------------------------------
    // Initialize & Check System Engine
    // ----------------------------------------------------
    fetch("/api/system")
        .then(res => res.json())
        .then(data => {
            const badge = document.getElementById("systemBadge");
            if (data.ffmpeg_available) {
                badge.innerHTML = `<span class="status-dot"></span><span>Hardware Acceleration Ready</span>`;
            } else {
                badge.innerHTML = `<span class="status-dot" style="background:#F59E0B;box-shadow:0 0 10px #F59E0B"></span><span>FFmpeg Standard Mode</span>`;
            }
        })
        .catch(console.error);

    // ----------------------------------------------------
    // Drag & Drop & Upload Handling
    // ----------------------------------------------------
    ['dragenter', 'dragover'].forEach(eventName => {
        dropzone.addEventListener(eventName, (e) => {
            e.preventDefault();
            e.stopPropagation();
            dropzone.classList.add('dragover');
        }, false);
    });

    ['dragleave', 'drop'].forEach(eventName => {
        dropzone.addEventListener(eventName, (e) => {
            e.preventDefault();
            e.stopPropagation();
            dropzone.classList.remove('dragover');
        }, false);
    });

    dropzone.addEventListener('drop', (e) => {
        const dt = e.dataTransfer;
        const files = dt.files;
        if (files && files.length > 0) {
            handleFileUpload(files[0]);
        }
    });

    videoInput.addEventListener('change', (e) => {
        if (e.target.files && e.target.files.length > 0) {
            handleFileUpload(e.target.files[0]);
        }
    });

    function formatBytes(bytes) {
        if (bytes < 1024) return bytes + ' B';
        if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
        if (bytes < 1024 * 1024 * 1024) return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
        return (bytes / (1024 * 1024 * 1024)).toFixed(2) + ' GB';
    }

    function handleFileUpload(file) {
        if (!file.type.startsWith('video/') && !file.name.match(/\.(mp4|mkv|mov|avi|webm|flv|ts|m4v)$/i)) {
            showToast("Please select a valid video file.");
            return;
        }

        // Show upload progress UI
        uploadProgressContainer.style.display = "block";
        uploadProgressBar.style.width = "0%";
        uploadProgressPercent.innerText = "0%";
        uploadProgressLabel.innerText = `Uploading ${file.name}...`;

        const formData = new FormData();
        formData.append("video", file);

        const xhr = new XMLHttpRequest();
        const startTime = Date.now();

        xhr.upload.onprogress = (e) => {
            if (e.lengthComputable) {
                const percent = Math.round((e.loaded / e.total) * 100);
                uploadProgressBar.style.width = percent + "%";
                uploadProgressPercent.innerText = percent + "%";

                const elapsed = (Date.now() - startTime) / 1000;
                const speed = elapsed > 0 ? (e.loaded / elapsed) : 0;
                uploadStats.innerText = `${formatBytes(e.loaded)} / ${formatBytes(e.total)} (${formatBytes(speed)}/s)`;
            }
        };

        xhr.onload = () => {
            if (xhr.status === 200) {
                try {
                    const response = JSON.parse(xhr.responseText);
                    if (response.success) {
                        currentUploadedFile = response;
                        setupConfigStage(response);
                    } else {
                        showToast(response.error || "Upload failed");
                        uploadProgressContainer.style.display = "none";
                    }
                } catch (err) {
                    showToast("Error parsing server response");
                    uploadProgressContainer.style.display = "none";
                }
            } else {
                showToast("Upload failed: " + xhr.statusText);
                uploadProgressContainer.style.display = "none";
            }
        };

        xhr.onerror = () => {
            showToast("Network error during upload");
            uploadProgressContainer.style.display = "none";
        };

        xhr.open("POST", "/api/upload", true);
        xhr.send(formData);
    }

    // ----------------------------------------------------
    // Stage 2: Configuration & Estimation
    // ----------------------------------------------------
    function setupConfigStage(data) {
        uploadSection.style.display = "none";
        configSection.style.display = "block";

        const meta = data.metadata;
        videoFilename.innerText = data.filename;
        videoThumb.src = data.thumb_url;
        metaDuration.innerText = meta.duration_formatted;
        metaResolution.innerText = `${meta.width}x${meta.height}`;
        metaFps.innerText = `${meta.fps} fps`;
        metaSize.innerText = meta.file_size_formatted;

        updateReelEstimation();
    }

    function updateReelEstimation() {
        if (!currentUploadedFile) return;
        const totalDuration = currentUploadedFile.metadata.duration;
        const segLen = currentDuration;
        
        let count = Math.ceil(totalDuration / segLen);
        if (totalDuration <= segLen) count = 1;

        const minutes = Math.floor(segLen / 60);
        const seconds = segLen % 60;
        let durStr = "";
        if (minutes > 0) durStr += `${minutes} min `;
        if (seconds > 0) durStr += `${seconds} sec`;
        durStr = durStr.trim() || `${segLen}s`;

        reelsEstimateText.innerHTML = `This video will be sliced into <strong>${count} reels</strong> (${durStr} each)`;
    }

    // Preset buttons
    presetButtons.forEach(btn => {
        btn.addEventListener("click", () => {
            presetButtons.forEach(b => b.classList.remove("active"));
            btn.classList.add("active");
            currentDuration = parseFloat(btn.dataset.duration);
            customDuration.value = currentDuration;
            updateReelEstimation();
        });
    });

    customDuration.addEventListener("input", (e) => {
        const val = parseFloat(e.target.value);
        if (val > 0) {
            currentDuration = val;
            presetButtons.forEach(b => {
                if (parseFloat(b.dataset.duration) === val) {
                    b.classList.add("active");
                } else {
                    b.classList.remove("active");
                }
            });
            updateReelEstimation();
        }
    });

    // Mode Selection Cards
    modeCards.forEach(card => {
        card.addEventListener("click", () => {
            modeCards.forEach(c => c.classList.remove("selected"));
            card.classList.add("selected");
            const radio = card.querySelector('input[type="radio"]');
            if (radio) radio.checked = true;
        });
    });

    cancelConfigBtn.addEventListener("click", () => {
        configSection.style.display = "none";
        uploadSection.style.display = "block";
        uploadProgressContainer.style.display = "none";
        videoInput.value = "";
        currentUploadedFile = null;
    });

    // ----------------------------------------------------
    // Stage 3: Start Processing & Polling
    // ----------------------------------------------------
    startProcessBtn.addEventListener("click", () => {
        if (!currentUploadedFile) return;

        const selectedModeRadio = document.querySelector('input[name="cutMode"]:checked');
        const mode = selectedModeRadio ? selectedModeRadio.value : "fast";
        const overlap = parseFloat(overlapSelect.value) || 0;
        const prefix = prefixInput.value.trim() || "Reel";

        configSection.style.display = "none";
        processingSection.style.display = "block";

        fetch("/api/process", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                file_id: currentUploadedFile.file_id,
                segment_len: currentDuration,
                mode: mode,
                overlap: overlap,
                prefix: prefix
            })
        })
        .then(res => res.json())
        .then(data => {
            if (data.success) {
                currentTaskId = data.task_id;
                startPolling(data.task_id);
            } else {
                showToast(data.error || "Failed to start cutting process");
                processingSection.style.display = "none";
                configSection.style.display = "block";
            }
        })
        .catch(err => {
            showToast("Server error starting process");
            processingSection.style.display = "none";
            configSection.style.display = "block";
        });
    });

    function startPolling(taskId) {
        if (pollInterval) clearInterval(pollInterval);

        pollInterval = setInterval(() => {
            fetch(`/api/status/${taskId}`)
                .then(res => res.json())
                .then(status => {
                    if (status.error) {
                        clearInterval(pollInterval);
                        showToast(status.error);
                        return;
                    }

                    // Update UI
                    taskProgressBar.style.width = status.progress + "%";
                    taskPercent.innerText = status.progress + "%";
                    
                    if (status.total_clips > 0) {
                        taskClipCount.innerText = `Reel ${status.current_clip} of ${status.total_clips}`;
                    }

                    if (status.message) {
                        processingSubtitle.innerText = status.message;
                    }

                    if (status.status === "completed") {
                        clearInterval(pollInterval);
                        setTimeout(() => showResults(status), 500);
                    } else if (status.status === "error") {
                        clearInterval(pollInterval);
                        showToast(status.message || "An error occurred during video slicing");
                    }
                })
                .catch(console.error);
        }, 500);
    }

    // ----------------------------------------------------
    // Stage 4: Results Gallery & Downloads
    // ----------------------------------------------------
    function showResults(taskData) {
        processingSection.style.display = "none";
        resultsSection.style.display = "block";

        const clips = taskData.clips || [];
        resultsHeaderTitle.innerText = `${clips.length} Reels Generated in ${taskData.elapsed || 0}s`;
        resultsHeaderSubtitle.innerText = `All clips cut at ${currentDuration}s segments. Ready to post to YouTube Shorts, Reels, TikTok!`;

        // Render Cards
        reelsGrid.innerHTML = "";
        clips.forEach(clip => {
            const card = document.createElement("div");
            card.className = "reel-card";
            
            const thumbUrl = clip.has_thumb 
                ? `/api/thumb/${currentTaskId}/${clip.thumb_filename}` 
                : (currentUploadedFile ? currentUploadedFile.thumb_url : "");

            card.innerHTML = `
                <div class="reel-thumb-box" data-video="/api/stream/${currentTaskId}/${clip.filename}" data-title="${clip.filename}">
                    <img src="${thumbUrl}" alt="${clip.filename}" class="reel-thumb">
                    <div class="reel-play-btn">
                        <div class="play-circle">
                            <svg width="22" height="22" viewBox="0 0 24 24" fill="currentColor">
                                <polygon points="5 3 19 12 5 21 5 3"></polygon>
                            </svg>
                        </div>
                    </div>
                    <span class="reel-duration-badge">${clip.duration}s</span>
                </div>
                <div class="reel-info">
                    <h4 class="reel-number">Reel ${String(clip.index).padStart(2, '0')}</h4>
                    <p class="reel-timing">${clip.start_formatted} → ${clip.end_formatted}</p>
                    <div class="reel-footer">
                        <span class="reel-size">${clip.size_formatted}</span>
                        <a href="/api/download/${currentTaskId}/${clip.filename}" class="btn btn-primary reel-download-btn" download="${clip.filename}">
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
                                <polyline points="7 10 12 15 17 10"></polyline>
                                <line x1="12" y1="15" x2="12" y2="3"></line>
                            </svg>
                            Download
                        </a>
                    </div>
                </div>
            `;

            // Bind click to open preview modal
            const thumbBox = card.querySelector(".reel-thumb-box");
            thumbBox.addEventListener("click", () => {
                openVideoModal(`/api/stream/${currentTaskId}/${clip.filename}`, clip.filename, `/api/download/${currentTaskId}/${clip.filename}`);
            });

            reelsGrid.appendChild(card);
        });

        // Download All Button
        downloadAllBtn.onclick = () => {
            window.location.href = `/api/download-all/${currentTaskId}`;
        };

        // Open Folder Button
        openFolderBtn.onclick = () => {
            fetch("/api/open-folder", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ task_id: currentTaskId })
            })
            .then(res => res.json())
            .then(data => {
                if (data.success) {
                    showToast("Folder opened in Windows Explorer!");
                } else {
                    showToast("Could not open folder automatically");
                }
            })
            .catch(() => showToast("Folder opened in Windows Explorer!"));
        };
    }

    startNewVideoBtn.addEventListener("click", () => {
        resultsSection.style.display = "none";
        uploadSection.style.display = "block";
        uploadProgressContainer.style.display = "none";
        videoInput.value = "";
        currentUploadedFile = null;
        currentTaskId = null;
    });

    // ----------------------------------------------------
    // Video Modal Player
    // ----------------------------------------------------
    function openVideoModal(streamUrl, filename, downloadUrl) {
        modalVideoTitle.innerText = filename;
        modalVideoPlayer.src = streamUrl;
        modalDownloadBtn.href = downloadUrl;
        modalDownloadBtn.setAttribute("download", filename);
        videoModal.classList.add("active");
        modalVideoPlayer.play().catch(() => {});
    }

    function closeVideoModal() {
        modalVideoPlayer.pause();
        modalVideoPlayer.src = "";
        videoModal.classList.remove("active");
    }

    modalCloseBtn.addEventListener("click", closeVideoModal);
    modalBackdrop.addEventListener("click", closeVideoModal);
    document.addEventListener("keydown", (e) => {
        if (e.key === "Escape" && videoModal.classList.contains("active")) {
            closeVideoModal();
        }
    });

    // Toast helper
    function showToast(message) {
        toast.innerText = message;
        toast.classList.add("show");
        setTimeout(() => toast.classList.remove("show"), 3500);
    }
});
