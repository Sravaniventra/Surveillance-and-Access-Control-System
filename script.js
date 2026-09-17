/* =====================================================
   SECUREVISION ENTERPRISE SURVEILLANCE & ACCESS CONTROL
   Frontend Integration Script
   Preserving original layout, navigation, and components
   Enhanced with Real AI, Deep Learning & WebSocket Stream
===================================================== */

// State
let activeCameraId = "cam_01";
let currentFilter = "all";
let authToken = localStorage.getItem("securevision_token") || null;
let currentUploadedFile = null;
let ws = null;

/* =====================================================
   MODAL HELPERS
===================================================== */
function openModal(modalId) {
    const el = document.getElementById(modalId);
    if (el) el.classList.add("open");
}

function closeModal(modalId) {
    const el = document.getElementById(modalId);
    if (el) el.classList.remove("open");
}

window.openModal = openModal;
window.closeModal = closeModal;

/* =====================================================
   NAVIGATION
===================================================== */
const pages = document.querySelectorAll(".page");
const tabs = document.querySelectorAll(".top-tab");

function openPage(pageName) {
    pages.forEach(page => {
        page.classList.remove("active-page");
    });

    const target = document.getElementById(pageName);
    if (target) {
        target.classList.add("active-page");
    }

    tabs.forEach(tab => {
        tab.classList.remove("active");
        if (tab.dataset.page === pageName) {
            tab.classList.add("active");
        }
    });

    // Refresh page data on switch
    if (pageName === "records") {
        fetchRecords();
    } else if (pageName === "access") {
        fetchAccessLogs();
    } else if (pageName === "alerts") {
        fetchAlerts();
    } else if (pageName === "dashboard") {
        fetchDashboardStats();
    }
}

/* TOP TABS */
tabs.forEach(tab => {
    tab.addEventListener("click", () => {
        openPage(tab.dataset.page);
    });
});

/* QUICK ACTIONS */
document.querySelectorAll("[data-page-target]").forEach(button => {
    button.addEventListener("click", () => {
        openPage(button.dataset.pageTarget);
    });
});

/* =====================================================
   CLOCK & DATE
===================================================== */
function updateClock() {
    const now = new Date();
    let hours = now.getHours();
    const minutes = String(now.getMinutes()).padStart(2, "0");
    const seconds = String(now.getSeconds()).padStart(2, "0");
    const ampm = hours >= 12 ? "PM" : "AM";
    hours = hours % 12 || 12;

    const time = `${String(hours).padStart(2, "0")}:${minutes}:${seconds}`;
    const fullTime = `${String(hours).padStart(2, "0")}:${minutes}:${seconds} ${ampm}`;

    const topClock = document.getElementById("topClock");
    const commandClock = document.getElementById("commandClock");

    if (topClock) topClock.textContent = time;
    if (commandClock) commandClock.textContent = fullTime;

    const months = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"];
    const dateText = `${String(now.getDate()).padStart(2, "0")} ${months[now.getMonth()]} ${now.getFullYear()}`;
    const dateElement = document.getElementById("fullDate");
    if (dateElement) dateElement.textContent = dateText;
}
updateClock();
setInterval(updateClock, 1000);

/* =====================================================
   CAMERA SELECTION & SWITCHING
===================================================== */
const locations = document.querySelectorAll(".location");
const miniCameras = document.querySelectorAll(".mini-camera");
const cameraMetaMap = {
    "cam_01": { name: "CAM 01", location: "Main Entrance", meta: "CAM-01 / MAIN" },
    "cam_02": { name: "CAM 02", location: "Reception", meta: "CAM-02 / RECEPTION" },
    "cam_03": { name: "CAM 03", location: "R&D Laboratory", meta: "CAM-03 / LAB (RESTRICTED)" },
    "cam_04": { name: "CAM 04", location: "Side Gate", meta: "CAM-04 / SIDE GATE" }
};

function selectCamera(camId) {
    activeCameraId = camId;
    const streamImg = document.getElementById("cameraStreamImg");
    if (streamImg) {
        streamImg.src = `/api/video_feed/${camId}?t=${Date.now()}`;
        streamImg.style.display = "block";
    }

    const info = cameraMetaMap[camId] || { name: camId.toUpperCase(), location: "Sector View", meta: camId };
    const nameEl = document.getElementById("primaryCamName");
    const locEl = document.getElementById("primaryCamLocation");
    const metaEl = document.getElementById("cameraMetaName");

    if (nameEl) nameEl.textContent = info.name;
    if (locEl) locEl.textContent = info.location.toUpperCase();
    if (metaEl) metaEl.textContent = info.meta;

    // Update active state on location buttons
    locations.forEach(btn => {
        if (btn.dataset.camId === camId) {
            btn.classList.add("active");
        } else {
            btn.classList.remove("active");
        }
    });

    // Update active state on mini cameras
    miniCameras.forEach(mini => {
        if (mini.dataset.camId === camId) {
            mini.classList.add("selected");
        } else {
            mini.classList.remove("selected");
        }
    });
}

locations.forEach(location => {
    location.addEventListener("click", () => {
        const camId = location.dataset.camId || "cam_01";
        selectCamera(camId);
    });
});

miniCameras.forEach(camera => {
    camera.addEventListener("click", () => {
        const camId = camera.dataset.camId || "cam_01";
        selectCamera(camId);
    });
});

// Camera Source Switcher (Webcam <-> Dataset Feed)
const cameraSourceBtn = document.getElementById("cameraSourceBtn");
let isWebcam = false;
if (cameraSourceBtn) {
    cameraSourceBtn.addEventListener("click", async () => {
        isWebcam = !isWebcam;
        const sourceType = isWebcam ? "webcam" : "cctv_dataset";
        try {
            const res = await fetch(`/api/cameras/${activeCameraId}/source?source_type=${sourceType}`, { method: "POST" });
            if (res.ok) {
                cameraSourceBtn.classList.toggle("active", isWebcam);
                cameraSourceBtn.title = isWebcam ? "Active: Webcam 0 (Click for CCTV Dataset)" : "Active: CCTV Dataset (Click for Webcam)";
                selectCamera(activeCameraId);
            }
        } catch (e) {
            console.error("Failed to switch camera source:", e);
        }
    });
}

// Camera Online / Offline Toggle
const cameraToggleOnlineBtn = document.getElementById("cameraToggleOnlineBtn");
if (cameraToggleOnlineBtn) {
    cameraToggleOnlineBtn.addEventListener("click", async () => {
        try {
            const res = await fetch(`/api/cameras/${activeCameraId}/toggle`, { method: "POST" });
            const data = await res.json();
            const footerBadge = document.getElementById("footerOnlineBadge");
            const statusBadge = document.getElementById("primaryCamStatus");
            if (data.is_online) {
                if (footerBadge) footerBadge.innerHTML = '<i class="fa-solid fa-circle"></i> ONLINE';
                if (statusBadge) statusBadge.innerHTML = '<i></i> LIVE';
            } else {
                if (footerBadge) footerBadge.innerHTML = '<i class="fa-solid fa-circle" style="color:var(--red);"></i> OFFLINE';
                if (statusBadge) statusBadge.innerHTML = '<i style="background:var(--red);"></i> OFFLINE';
            }
            fetchDashboardStats();
        } catch (e) {
            console.error("Failed to toggle camera:", e);
        }
    });
}

// Expand button
const expandCamBtn = document.getElementById("expandCamBtn");
if (expandCamBtn) {
    expandCamBtn.addEventListener("click", () => {
        const viewport = document.querySelector(".camera-viewport");
        if (viewport) {
            if (!document.fullscreenElement) {
                viewport.requestFullscreen().catch(err => alert(`Fullscreen error: ${err.message}`));
            } else {
                document.exitFullscreen();
            }
        }
    });
}

/* =====================================================
   DASHBOARD STATS & RECENT ACTIVITY
===================================================== */
async function fetchDashboardStats() {
    try {
        const res = await fetch("/api/dashboard/stats");
        if (!res.ok) return;
        const data = await res.json();

        const railCam = document.getElementById("railCameraCount");
        const railId = document.getElementById("railIdentityCount");
        const railVis = document.getElementById("railVisitorCount");
        const railAlert = document.getElementById("railAlertCount");
        const topBadge = document.getElementById("topAlertBadge");

        if (railCam) railCam.textContent = String(data.total_cameras).padStart(2, "0");
        if (railId) railId.textContent = String(data.total_identities).padStart(2, "0");
        if (railVis) railVis.textContent = String(data.active_visitors).padStart(2, "0");
        if (railAlert) railAlert.textContent = String(data.today_alerts).padStart(2, "0");
        if (topBadge) topBadge.textContent = String(data.today_alerts);

        const facScore = document.getElementById("facilityScore");
        const facStatus = document.getElementById("facilityStatusText");
        const accessCount = document.getElementById("statAccessCount");
        const blockedCount = document.getElementById("statBlockedCount");
        const visCount = document.getElementById("statActiveVisitors");

        if (facScore) facScore.textContent = `${data.security_score}%`;
        if (facStatus) facStatus.textContent = data.system_status;
        if (accessCount) accessCount.textContent = data.today_access_count;
        if (blockedCount) blockedCount.textContent = String(data.today_blocked_count).padStart(2, "0");
        if (visCount) visCount.textContent = String(data.active_visitors).padStart(2, "0");
    } catch (e) {
        console.error("Error fetching dashboard stats:", e);
    }
}

async function fetchRecentActivity() {
    try {
        const res = await fetch("/api/access_logs?limit=5");
        if (!res.ok) return;
        const logs = await res.json();
        const container = document.getElementById("activityList");
        if (!container) return;

        if (logs.length === 0) return;

        container.innerHTML = logs.map(log => {
            const timeStr = new Date(log.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
            let markerClass = "danger-marker";
            let markerIcon = "fa-triangle-exclamation";
            let rowClass = "danger-row";
            let statusClass = "denied";

            if (log.status === "GRANTED") {
                markerClass = "success-marker";
                markerIcon = "fa-user-check";
                rowClass = "";
                statusClass = "granted";
            } else if (log.status === "CHECKED IN") {
                markerClass = "visitor-marker";
                markerIcon = "fa-user";
                rowClass = "";
                statusClass = "visitor-status";
            }

            return `
                <div class="activity-item ${rowClass}">
                    <div class="activity-time">${timeStr}</div>
                    <div class="activity-marker ${markerClass}">
                        <i class="fa-solid ${markerIcon}"></i>
                    </div>
                    <div class="activity-details">
                        <strong>${log.identity_name}</strong>
                        <span>${log.location} • ${log.camera_name}</span>
                    </div>
                    <b class="activity-status ${statusClass}">${log.status}</b>
                </div>
            `;
        }).join("");
    } catch (e) {
        console.error("Error fetching recent activity:", e);
    }
}

/* =====================================================
   FACE RECOGNITION (IMAGE UPLOAD & REAL ML INFERENCE)
===================================================== */
const imageInput = document.getElementById("imageInput");
const uploadedImage = document.getElementById("uploadedImage");
const uploadContent = document.querySelector(".upload-content");
const faceBox = document.getElementById("faceBox");
const processButton = document.getElementById("processButton");

if (imageInput) {
    imageInput.addEventListener("change", function (event) {
        const file = event.target.files[0];
        if (!file) return;

        currentUploadedFile = file;
        const reader = new FileReader();
        reader.onload = function (e) {
            uploadedImage.src = e.target.result;
            uploadedImage.style.display = "block";
            if (uploadContent) uploadContent.style.display = "none";
            if (faceBox) faceBox.style.display = "none";
        };
        reader.readAsDataURL(file);
        updateRecognitionTime();
    });
}

if (processButton) {
    processButton.addEventListener("click", async function () {
        if (!currentUploadedFile && (!uploadedImage.src || uploadedImage.style.display === "none")) {
            alert("Please upload a surveillance or dataset image first.");
            return;
        }

        const result = document.getElementById("recognitionResult");
        const access = document.getElementById("accessResult");
        const circle = document.getElementById("statusCircle");

        result.textContent = "ANALYZING";
        access.textContent = "YuNet face detection & SFace deep feature extraction in progress...";
        circle.className = "status-circle";
        circle.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i>';
        processButton.disabled = true;

        try {
            const formData = new FormData();
            if (currentUploadedFile) {
                formData.append("image", currentUploadedFile);
            } else {
                // Fetch blob from base64
                const blob = await fetch(uploadedImage.src).then(r => r.blob());
                formData.append("image", blob, "surveillance.jpg");
            }
            formData.append("camera_id", activeCameraId);

            const response = await fetch("/api/recognize", {
                method: "POST",
                body: formData
            });

            if (!response.ok) {
                throw new Error("Recognition server error");
            }

            const data = await response.json();

            if (!data.face_detected) {
                result.textContent = "NO FACE DETECTED";
                access.textContent = "No human face found in image area";
                circle.className = "status-circle denied";
                circle.innerHTML = '<i class="fa-solid fa-question"></i>';

                document.getElementById("employeeId").textContent = "---";
                document.getElementById("employeeName").textContent = "None Detected";
                document.getElementById("department").textContent = "---";
                document.getElementById("designation").textContent = "---";
                document.getElementById("accessLevel").textContent = "No Access";
                if (faceBox) faceBox.style.display = "none";
            } else if (!data.is_live) {
                result.textContent = "SPOOF DETECTED";
                access.textContent = "Anti-Spoofing: Replay / Photo Print Rejected";
                circle.className = "status-circle denied";
                circle.innerHTML = '<i class="fa-solid fa-triangle-exclamation"></i>';

                document.getElementById("employeeId").textContent = "SPOOF-ALERT";
                document.getElementById("employeeName").textContent = "Suspected Replay Attack";
                document.getElementById("department").textContent = "Biometric Security";
                document.getElementById("designation").textContent = `Liveness Score: ${data.liveness_score}`;
                document.getElementById("accessLevel").textContent = "DENIED";

                positionFaceBox(data.box, "#ff4d4d");
            } else if (data.authorized && data.identity) {
                const isEmp = data.classification === "EMPLOYEE";
                result.textContent = isEmp ? "MATCH FOUND" : "VISITOR VERIFIED";
                access.textContent = data.message || "Access Granted";
                circle.className = isEmp ? "status-circle success" : "status-circle visitor-circle";
                circle.innerHTML = '<i class="fa-solid fa-check"></i>';

                document.getElementById("employeeId").textContent = data.identity.id;
                document.getElementById("employeeName").textContent = data.identity.name;
                document.getElementById("department").textContent = data.identity.department;
                document.getElementById("designation").textContent = data.identity.designation;
                document.getElementById("accessLevel").textContent = data.identity.access_level;

                positionFaceBox(data.box, data.badge_color);
            } else {
                result.textContent = "UNKNOWN PERSON";
                access.textContent = data.message || "Access Denied";
                circle.className = "status-circle denied";
                circle.innerHTML = '<i class="fa-solid fa-xmark"></i>';

                document.getElementById("employeeId").textContent = "UNKNOWN";
                document.getElementById("employeeName").textContent = "Unregistered Individual";
                document.getElementById("department").textContent = "---";
                document.getElementById("designation").textContent = `Cosine Match: ${data.similarity_score}`;
                document.getElementById("accessLevel").textContent = "No Access";

                positionFaceBox(data.box, "#ff4d4d");
            }

            document.getElementById("timestamp").textContent = data.timestamp;
            fetchDashboardStats();
        } catch (err) {
            console.error(err);
            result.textContent = "PROCESSING ERROR";
            access.textContent = "Could not communicate with deep learning backend.";
            circle.className = "status-circle denied";
            circle.innerHTML = '<i class="fa-solid fa-triangle-exclamation"></i>';
        } finally {
            processButton.disabled = false;
        }
    });
}

function positionFaceBox(box, color) {
    if (!faceBox || !box) return;
    const img = uploadedImage;
    if (!img.naturalWidth || !img.naturalHeight) {
        faceBox.style.display = "none";
        return;
    }

    const scaleX = img.clientWidth / img.naturalWidth;
    const scaleY = img.clientHeight / img.naturalHeight;

    const [bx, by, bw, bh] = box;
    const left = img.offsetLeft + (bx * scaleX);
    const top = img.offsetTop + (by * scaleY);
    const width = bw * scaleX;
    const height = bh * scaleY;

    faceBox.style.left = `${left}px`;
    faceBox.style.top = `${top}px`;
    faceBox.style.width = `${width}px`;
    faceBox.style.height = `${height}px`;
    faceBox.style.borderColor = color;
    faceBox.style.display = "block";
}

function updateRecognitionTime() {
    const element = document.getElementById("recognitionTime");
    const timestamp = document.getElementById("timestamp");
    if (!element && !timestamp) return;

    const now = new Date();
    let hours = now.getHours();
    const minutes = String(now.getMinutes()).padStart(2, "0");
    const seconds = String(now.getSeconds()).padStart(2, "0");
    const ampm = hours >= 12 ? "PM" : "AM";
    hours = hours % 12 || 12;

    const formatted = `${String(now.getDate()).padStart(2, "0")}-${String(now.getMonth() + 1).padStart(2, "0")}-${now.getFullYear()} ${hours}:${minutes}:${seconds} ${ampm}`;

    if (element) element.textContent = formatted;
    if (timestamp && timestamp.textContent.includes("Waiting")) {
        timestamp.textContent = formatted;
    }
}

/* =====================================================
   ATTENDANCE & RECORDS TABLE
===================================================== */
async function fetchRecords(filter = currentFilter, search = "") {
    try {
        const url = `/api/records?filter_type=${filter}&search=${encodeURIComponent(search)}`;
        const res = await fetch(url);
        if (!res.ok) return;
        const records = await res.json();
        const tbody = document.getElementById("recordsTableBody");
        if (!tbody) return;

        if (records.length === 0) {
            tbody.innerHTML = `<tr><td colspan="5" style="text-align: center; color: var(--muted); padding: 24px;">No records found.</td></tr>`;
            return;
        }

        tbody.innerHTML = records.map(r => {
            const timeStr = new Date(r.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
            let badgeClass = "table-danger";
            if (r.status === "GRANTED") badgeClass = "table-success";
            else if (r.status === "CHECKED IN") badgeClass = "table-info";

            return `
                <tr>
                    <td>${timeStr}</td>
                    <td><strong>${r.identity_name}</strong> <small style="color:var(--muted)">(${r.identity_code})</small></td>
                    <td>${r.identity_type}</td>
                    <td>${r.location}</td>
                    <td><span class="${badgeClass}">${r.status}</span></td>
                </tr>
            `;
        }).join("");
    } catch (e) {
        console.error("Error loading records:", e);
    }
}

// Filter buttons on records page
document.querySelectorAll(".data-toolbar .filter-button").forEach(btn => {
    btn.addEventListener("click", () => {
        document.querySelectorAll(".data-toolbar .filter-button").forEach(b => b.classList.remove("active"));
        btn.classList.add("active");
        currentFilter = btn.dataset.filter || "all";
        const searchVal = document.getElementById("recordsSearchInput")?.value || "";
        fetchRecords(currentFilter, searchVal);
    });
});

// Search input on records page
const searchInput = document.getElementById("recordsSearchInput");
if (searchInput) {
    let debounceTimer = null;
    searchInput.addEventListener("input", (e) => {
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(() => {
            fetchRecords(currentFilter, e.target.value);
        }, 300);
    });
}

// Export CSV / JSON
const exportCsvBtn = document.getElementById("exportCsvBtn");
if (exportCsvBtn) {
    exportCsvBtn.addEventListener("click", () => {
        window.open("/api/records/export?format=csv", "_blank");
    });
}

const exportJsonBtn = document.getElementById("exportJsonBtn");
if (exportJsonBtn) {
    exportJsonBtn.addEventListener("click", () => {
        window.open("/api/records/export?format=json", "_blank");
    });
}

/* =====================================================
   ACCESS TIMELINE
===================================================== */
async function fetchAccessLogs() {
    try {
        const res = await fetch("/api/access_logs?limit=25");
        if (!res.ok) return;
        const logs = await res.json();
        const container = document.getElementById("accessTimeline");
        if (!container) return;

        if (logs.length === 0) {
            container.innerHTML = `<p style="color:var(--muted); text-align:center; padding: 20px;">No access events recorded yet.</p>`;
            return;
        }

        container.innerHTML = logs.map(l => {
            const timeStr = new Date(l.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
            const isGranted = l.status === "GRANTED";
            const entryClass = isGranted ? "granted-entry" : "denied-entry";
            const iconClass = isGranted ? "fa-check" : "fa-xmark";

            return `
                <div class="timeline-entry ${entryClass}">
                    <div class="timeline-time">${timeStr}</div>
                    <div class="timeline-icon"><i class="fa-solid ${iconClass}"></i></div>
                    <div>
                        <strong>Access ${l.status === "GRANTED" ? "Granted" : (l.status === "CHECKED IN" ? "Checked In" : "Denied")}</strong>
                        <span>${l.identity_name} (${l.identity_code}) • ${l.location} [${l.camera_name}]</span>
                    </div>
                </div>
            `;
        }).join("");
    } catch (e) {
        console.error("Error loading access timeline:", e);
    }
}

/* =====================================================
   SECURITY ALERTS & INVESTIGATION LIFECYCLE
===================================================== */
let currentAlertsList = [];

async function fetchAlerts() {
    try {
        const res = await fetch("/api/alerts?limit=20");
        if (!res.ok) return;
        currentAlertsList = await res.json();

        const majorContainer = document.getElementById("majorAlertContainer");
        const smallContainer = document.getElementById("smallAlertsContainer");

        if (currentAlertsList.length === 0) {
            if (majorContainer) majorContainer.style.display = "none";
            if (smallContainer) smallContainer.innerHTML = `<p style="color:var(--muted); padding:20px;">All security clear. No active alerts.</p>`;
            return;
        }

        // Render Top Alert (Major)
        const topAlert = currentAlertsList[0];
        if (majorContainer) {
            majorContainer.style.display = "grid";
            const dateStr = new Date(topAlert.timestamp).toLocaleString();
            majorContainer.innerHTML = `
                <div class="major-alert-icon">
                    <i class="fa-solid fa-triangle-exclamation"></i>
                </div>
                <div>
                    <span style="display:flex; align-items:center; gap:8px;">
                        ${topAlert.severity} EVENT 
                        <span class="alert-status-badge ${topAlert.status.toLowerCase()}">${topAlert.status}</span>
                    </span>
                    <h3>${topAlert.alert_type.replace(/_/g, " ")}: ${topAlert.identity_name}</h3>
                    <p>${topAlert.description}</p>
                    <small>${dateStr} • ${topAlert.location} • ${topAlert.camera_name}</small>
                </div>
                <button onclick="openAlertReviewModal(${topAlert.id})">
                    REVIEW EVENT
                </button>
            `;
        }

        // Render remaining alerts (Small)
        if (smallContainer) {
            const others = currentAlertsList.slice(1);
            if (others.length === 0) {
                smallContainer.innerHTML = "";
            } else {
                smallContainer.innerHTML = others.map(a => {
                    const timeStr = new Date(a.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
                    return `
                        <div class="alert-card-small" style="cursor: pointer;" onclick="openAlertReviewModal(${a.id})">
                            <i class="fa-solid fa-user-slash"></i>
                            <div>
                                <strong>${a.alert_type.replace(/_/g, " ")}: ${a.identity_name}</strong>
                                <span>${a.location} • ${timeStr}</span>
                            </div>
                            <span class="alert-status-badge ${a.status.toLowerCase()}">${a.status}</span>
                        </div>
                    `;
                }).join("");
            }
        }
    } catch (e) {
        console.error("Error loading alerts:", e);
    }
}

window.openAlertReviewModal = function (alertId) {
    const alert = currentAlertsList.find(a => a.id === alertId);
    if (!alert) return;

    document.getElementById("reviewAlertId").value = alert.id;
    document.getElementById("reviewAlertDesc").textContent = `${alert.alert_type}: ${alert.description} [${alert.location}]`;
    document.getElementById("reviewAlertStatus").value = alert.status;
    document.getElementById("reviewAlertNotes").value = alert.resolution_notes || "";

    const snapImg = document.getElementById("reviewSnapshotImg");
    if (alert.snapshot_path) {
        snapImg.src = alert.snapshot_path;
        snapImg.style.display = "block";
    } else {
        snapImg.style.display = "none";
    }

    const msg = document.getElementById("reviewAlertMsg");
    if (msg) msg.style.display = "none";

    openModal("alertReviewModal");
};

const saveAlertReviewBtn = document.getElementById("saveAlertReviewBtn");
if (saveAlertReviewBtn) {
    saveAlertReviewBtn.addEventListener("click", async () => {
        const id = document.getElementById("reviewAlertId").value;
        const statusVal = document.getElementById("reviewAlertStatus").value;
        const notes = document.getElementById("reviewAlertNotes").value;
        const msg = document.getElementById("reviewAlertMsg");

        saveAlertReviewBtn.disabled = true;
        try {
            const res = await fetch(`/api/alerts/${id}/status`, {
                method: "PATCH",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ status: statusVal, resolution_notes: notes })
            });

            if (res.ok) {
                if (msg) {
                    msg.textContent = "Status updated successfully!";
                    msg.style.color = "var(--green)";
                    msg.style.display = "block";
                }
                setTimeout(() => {
                    closeModal("alertReviewModal");
                    fetchAlerts();
                    fetchDashboardStats();
                }, 700);
            } else {
                throw new Error("Failed to update status");
            }
        } catch (e) {
            if (msg) {
                msg.textContent = "Error saving resolution";
                msg.style.color = "var(--red)";
                msg.style.display = "block";
            }
        } finally {
            saveAlertReviewBtn.disabled = false;
        }
    });
}

/* =====================================================
   ADMIN LOGIN & PROFILE
===================================================== */
const adminBtn = document.getElementById("adminBtn");
const adminLoginForm = document.getElementById("adminLoginForm");
const adminProfileView = document.getElementById("adminProfileView");

if (adminBtn) {
    adminBtn.addEventListener("click", async () => {
        checkAdminAuthStatus();
        openModal("adminModal");
    });
}

async function checkAdminAuthStatus() {
    if (!authToken) {
        showLoginForm();
        return;
    }
    try {
        const res = await fetch("/api/auth/me", {
            headers: { "Authorization": `Bearer ${authToken}` }
        });
        const data = await res.json();
        if (data.authenticated) {
            showProfileView(data.full_name || data.username);
        } else {
            showLoginForm();
        }
    } catch {
        showLoginForm();
    }
}

function showLoginForm() {
    if (adminLoginForm) adminLoginForm.style.display = "flex";
    if (adminProfileView) adminProfileView.style.display = "none";
    document.getElementById("adminModalTitle").textContent = "Admin Authentication";
}

function showProfileView(name) {
    if (adminLoginForm) adminLoginForm.style.display = "none";
    if (adminProfileView) adminProfileView.style.display = "block";
    document.getElementById("adminModalTitle").textContent = "Admin Control Portal";
    document.getElementById("adminProfileName").textContent = name;
}

const adminSubmitLoginBtn = document.getElementById("adminSubmitLoginBtn");
if (adminSubmitLoginBtn) {
    adminSubmitLoginBtn.addEventListener("click", async () => {
        const user = document.getElementById("adminUsername").value.trim();
        const pass = document.getElementById("adminPassword").value.trim();
        const errEl = document.getElementById("adminLoginError");

        if (!user || !pass) {
            if (errEl) {
                errEl.textContent = "Please enter both username and password.";
                errEl.style.display = "block";
            }
            return;
        }

        adminSubmitLoginBtn.disabled = true;
        try {
            const res = await fetch("/api/auth/login", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ username: user, password: pass })
            });
            const data = await res.json();
            if (res.ok && data.access_token) {
                authToken = data.access_token;
                localStorage.setItem("securevision_token", authToken);
                if (errEl) errEl.style.display = "none";
                showProfileView(data.username);
            } else {
                if (errEl) {
                    errEl.textContent = data.detail || "Authentication failed.";
                    errEl.style.display = "block";
                }
            }
        } catch (e) {
            if (errEl) {
                errEl.textContent = "Cannot connect to auth server.";
                errEl.style.display = "block";
            }
        } finally {
            adminSubmitLoginBtn.disabled = false;
        }
    });
}

const adminLogoutBtn = document.getElementById("adminLogoutBtn");
if (adminLogoutBtn) {
    adminLogoutBtn.addEventListener("click", () => {
        authToken = null;
        localStorage.removeItem("securevision_token");
        showLoginForm();
    });
}

/* =====================================================
   FACE ENROLLMENT
===================================================== */
const enrollFaceBtn = document.getElementById("enrollFaceBtn");
const openEnrollFromAdminBtn = document.getElementById("openEnrollFromAdminBtn");
const enrollForm = document.getElementById("enrollForm");

function triggerEnrollModal() {
    closeModal("adminModal");
    openModal("enrollModal");
}

if (enrollFaceBtn) enrollFaceBtn.addEventListener("click", triggerEnrollModal);
if (openEnrollFromAdminBtn) openEnrollFromAdminBtn.addEventListener("click", triggerEnrollModal);

if (enrollForm) {
    enrollForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        const code = document.getElementById("enrollCode").value.trim();
        const name = document.getElementById("enrollName").value.trim();
        const type = document.getElementById("enrollType").value;
        const dept = document.getElementById("enrollDept").value.trim();
        const desig = document.getElementById("enrollDesig").value.trim();
        const level = document.getElementById("enrollLevel").value;
        const cams = document.getElementById("enrollCameras").value.trim();
        const photoFile = document.getElementById("enrollPhoto").files[0];
        const msg = document.getElementById("enrollMessage");
        const submitBtn = document.getElementById("enrollSubmitBtn");

        if (!photoFile) {
            alert("Please select a face photo file.");
            return;
        }

        submitBtn.disabled = true;
        msg.textContent = "Detecting face and computing deep biometrics...";
        msg.style.color = "var(--blue)";
        msg.style.display = "block";

        const formData = new FormData();
        formData.append("identity_code", code);
        formData.append("name", name);
        formData.append("identity_type", type);
        formData.append("department", dept);
        formData.append("designation", desig);
        formData.append("access_level", level);
        formData.append("allowed_cameras", cams);
        formData.append("photo", photoFile);

        try {
            const res = await fetch("/api/enroll", {
                method: "POST",
                body: formData
            });
            const data = await res.json();
            if (res.ok) {
                msg.textContent = `Enrolled ${data.name} (${data.identity_code}) successfully!`;
                msg.style.color = "var(--green)";
                setTimeout(() => {
                    enrollForm.reset();
                    closeModal("enrollModal");
                    fetchDashboardStats();
                }, 1200);
            } else {
                msg.textContent = data.detail || "Enrollment failed.";
                msg.style.color = "var(--red)";
            }
        } catch (e) {
            msg.textContent = "Server connection error.";
            msg.style.color = "var(--red)";
        } finally {
            submitBtn.disabled = false;
        }
    });
}

/* =====================================================
   WEBSOCKET REAL-TIME STREAM
===================================================== */
function initWebSocket() {
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const host = window.location.host || "localhost:8000";
    const wsUrl = `${protocol}//${host}/ws`;

    ws = new WebSocket(wsUrl);

    ws.onopen = () => {
        console.log("[WebSocket] Connected to SecureVision Server");
    };

    ws.onmessage = (event) => {
        try {
            const msg = JSON.parse(event.data);
            if (msg.type === "new_alert") {
                // Update top and rail alerts
                const railAlert = document.getElementById("railAlertCount");
                const topBadge = document.getElementById("topAlertBadge");
                if (railAlert) {
                    const curr = parseInt(railAlert.textContent) || 0;
                    railAlert.textContent = String(curr + 1).padStart(2, "0");
                }
                if (topBadge) {
                    const curr = parseInt(topBadge.textContent) || 0;
                    topBadge.textContent = String(curr + 1);
                }
                fetchAlerts();
            } else if (msg.type === "new_activity") {
                fetchRecentActivity();
                fetchDashboardStats();
            } else if (msg.type === "new_enrollment") {
                fetchDashboardStats();
            }
        } catch (e) {
            console.error("[WebSocket] Message parsing error:", e);
        }
    };

    ws.onclose = () => {
        console.log("[WebSocket] Disconnected. Reconnecting in 3s...");
        setTimeout(initWebSocket, 3000);
    };

    ws.onerror = (err) => {
        console.error("[WebSocket] Error:", err);
    };
}

/* =====================================================
   INITIALIZATION ON LOAD
===================================================== */
window.addEventListener("DOMContentLoaded", () => {
    initWebSocket();
    fetchDashboardStats();
    fetchRecentActivity();
    fetchRecords();
    fetchAccessLogs();
    fetchAlerts();
});