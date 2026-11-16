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
    const videoUrlInput = document.getElementById("videoUrlInput");
    const fetchUrlBtn = document.getElementById("fetchUrlBtn");

    // Quality Selector Elements
    const qualityModal = document.getElementById("qualityModal");
    const qualityModalBackdrop = document.getElementById("qualityModalBackdrop");
    const qualityModalCloseBtn = document.getElementById("qualityModalCloseBtn");
    const qualityCancelBtn = document.getElementById("qualityCancelBtn");
    const confirmQualityBtn = document.getElementById("confirmQualityBtn");
    const qualityThumb = document.getElementById("qualityThumb");
    const qualityVideoName = document.getElementById("qualityVideoName");
    const qualityUploader = document.getElementById("qualityUploader");
    const qualityDuration = document.getElementById("qualityDuration");
    const qualityOptionsList = document.getElementById("qualityOptionsList");
    let currentProbeInfo = null;
    
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

    // ----------------------------------------------------
    // URL Link Inspection & Quality Selection
    // ----------------------------------------------------
    if (fetchUrlBtn && videoUrlInput) {
        fetchUrlBtn.addEventListener("click", handleUrlFetch);
        videoUrlInput.addEventListener("keydown", (e) => {
            if (e.key === "Enter") {
                e.preventDefault();
                handleUrlFetch();
            }
        });
    }

    function closeQualityModal() {
        qualityModal.classList.remove("active");
        fetchUrlBtn.disabled = false;
        fetchUrlBtn.innerHTML = `
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
                <polygon points="5 3 19 12 5 21 5 3"></polygon>
            </svg>
            Fetch & Cut
        `;
    }

    if (qualityModalCloseBtn) qualityModalCloseBtn.addEventListener("click", closeQualityModal);
    if (qualityModalBackdrop) qualityModalBackdrop.addEventListener("click", closeQualityModal);
    if (qualityCancelBtn) qualityCancelBtn.addEventListener("click", closeQualityModal);

    function handleUrlFetch() {
        const url = videoUrlInput.value.trim();
        if (!url) {
            showToast("Please paste a valid video URL.");
            return;
        }

        // Show inspecting state on button
        fetchUrlBtn.disabled = true;
        fetchUrlBtn.innerHTML = `
            <span class="spinner" style="width:16px;height:16px;border-width:2px;display:inline-block;margin-right:6px;"></span>
            Inspecting...
        `;

        // 1. Probe video metadata first to show qualities and sizes
        fetch("/api/probe-url", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ url: url })
        })
        .then(res => res.json())
        .then(data => {
            fetchUrlBtn.disabled = false;
            fetchUrlBtn.innerHTML = `
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
                    <polygon points="5 3 19 12 5 21 5 3"></polygon>
                </svg>
                Fetch & Cut
            `;

            if (data.success && data.info) {
                currentProbeInfo = data.info;
                showQualityModal(data.info);
            } else {
                showToast(data.error || "Could not inspect video stream");
            }
        })
        .catch(err => {
            fetchUrlBtn.disabled = false;
            fetchUrlBtn.innerHTML = `
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
                    <polygon points="5 3 19 12 5 21 5 3"></polygon>
                </svg>
                Fetch & Cut
            `;
            showToast("Network error inspecting video URL");
        });
    }

    function showQualityModal(info) {
        qualityVideoName.innerText = info.title;
        qualityVideoName.title = info.title;
        qualityThumb.src = info.thumbnail || "";
        qualityUploader.innerText = info.uploader || "Web Video";
        qualityDuration.innerText = info.duration_formatted || "00:00";

        // Render available quality cards
        qualityOptionsList.innerHTML = "";
        const qualities = info.qualities || [];

        if (qualities.length === 0) {
            qualities.push({
                quality_id: "720",
                height: 720,
                label: "720p HD (Default)",
                size_formatted: "Standard",
                format_spec: "best",
                recommended: true
            });
        }

        qualities.forEach((q, idx) => {
            const card = document.createElement("label");
            card.className = "quality-card" + (q.recommended ? " selected" : "");
            
            card.innerHTML = `
                <input type="radio" name="videoQualityOption" value="${q.format_spec}" ${q.recommended ? "checked" : ""}>
                <div class="quality-card-left">
                    <div class="quality-res-badge">${q.height}p</div>
                    <div class="quality-details">
                        <span class="quality-name">${q.label}</span>
                        <span class="quality-desc">${q.recommended ? "★ Recommended quality & file size" : (q.height >= 1080 ? "Ultra sharp • Larger file" : "Fast download • Compact size")}</span>
                    </div>
                </div>
                <div class="quality-size-badge">${q.size_formatted}</div>
            `;

            card.addEventListener("click", () => {
                document.querySelectorAll(".quality-card").forEach(c => c.classList.remove("selected"));
                card.classList.add("selected");
                const radio = card.querySelector('input[type="radio"]');
                if (radio) radio.checked = true;
            });

            qualityOptionsList.appendChild(card);
        });

        qualityModal.classList.add("active");
    }

    // Confirm Quality & Start Download
    if (confirmQualityBtn) {
        confirmQualityBtn.addEventListener("click", () => {
            if (!currentProbeInfo) return;

            const selectedRadio = document.querySelector('input[name="videoQualityOption"]:checked');
            const formatSpec = selectedRadio ? selectedRadio.value : null;

            closeQualityModal();

            // Show download progress in upload container
            uploadProgressContainer.style.display = "block";
            uploadProgressBar.style.width = "5%";
            uploadProgressPercent.innerText = "5%";
            uploadProgressLabel.innerText = "Connecting to chosen stream...";
            uploadStats.innerText = "Initializing video download...";

            fetch("/api/fetch-url", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    url: currentProbeInfo.url,
                    format_spec: formatSpec
                })
            })
            .then(res => res.json())
            .then(data => {
                if (data.success && data.download_id) {
                    pollDownloadProgress(data.download_id);
                } else {
                    showToast(data.error || "Failed to start download");
                    uploadProgressContainer.style.display = "none";
                }
            })
            .catch(err => {
                showToast("Network error starting download");
                uploadProgressContainer.style.display = "none";
            });
        });
    }

    function pollDownloadProgress(downloadId) {
        let dlInterval = setInterval(() => {
            fetch(`/api/fetch-status/${downloadId}`)
                .then(res => res.json())
                .then(status => {
                    if (status.status === "error") {
                        clearInterval(dlInterval);
                        fetchUrlBtn.disabled = false;
                        showToast(status.message || "Failed to download video from URL");
                        uploadProgressContainer.style.display = "none";
                        return;
                    }

                    const pct = Math.round(status.percent || 10);
                    uploadProgressBar.style.width = pct + "%";
                    uploadProgressPercent.innerText = pct + "%";
                    if (status.message) uploadProgressLabel.innerText = status.message;
                    if (status.speed) {
                        uploadStats.innerText = `${formatBytes(status.downloaded || 0)} / ${formatBytes(status.total || 0)} (${formatBytes(status.speed)}/s)`;
                    }

                    if (status.status === "completed" && status.result) {
                        clearInterval(dlInterval);
                        fetchUrlBtn.disabled = false;
                        videoUrlInput.value = "";
                        currentUploadedFile = status.result;
                        setupConfigStage(status.result);
                    }
                })
                .catch(err => {
                    clearInterval(dlInterval);
                    fetchUrlBtn.disabled = false;
                    showToast("Error checking download progress");
                });
        }, 500);
    }

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

    function discardUploadedFile() {
        if (currentUploadedFile && currentUploadedFile.file_id) {
            try {
                fetch("/api/discard", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ file_id: currentUploadedFile.file_id })
                }).catch(() => {});
            } catch (e) {}
        }
    }

    cancelConfigBtn.addEventListener("click", () => {
        discardUploadedFile();
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
        discardUploadedFile();
        resultsSection.style.display = "none";
        uploadSection.style.display = "block";
        uploadProgressContainer.style.display = "none";
        videoInput.value = "";
        currentUploadedFile = null;
        currentTaskId = null;
    });

    window.addEventListener("beforeunload", () => {
        if (currentUploadedFile && currentUploadedFile.file_id) {
            const blob = new Blob([JSON.stringify({ file_id: currentUploadedFile.file_id })], { type: 'application/json' });
            navigator.sendBeacon("/api/discard", blob);
        }
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
