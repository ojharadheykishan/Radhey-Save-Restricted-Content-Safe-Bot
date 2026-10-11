(() => {
    const video = document.querySelector('[data-video-player]');
    if (!(video instanceof HTMLVideoElement)) return;

    const controls = document.querySelector('[data-player-controls]');
    if (!controls) return;

    const currentTimeLabel = controls.querySelector('[data-player-time-current]');
    const durationLabel = controls.querySelector('[data-player-time-duration]');
    const seekControl = controls.querySelector('[data-player-seek]');
    const volumeControl = controls.querySelector('[data-player-volume]');
    const speedControl = controls.querySelector('[data-player-speed]');
    const qualityControl = controls.querySelector('[data-player-quality]');
    const message = controls.querySelector('[data-player-message]');
    const shell = video.closest('[data-player-shell]') || video;

    function formatTime(seconds) {
        if (!Number.isFinite(seconds) || seconds < 0) return '0:00';
        const total = Math.floor(seconds);
        const hours = Math.floor(total / 3600);
        const minutes = Math.floor((total % 3600) / 60);
        const remainder = String(total % 60).padStart(2, '0');
        return hours ? `${hours}:${String(minutes).padStart(2, '0')}:${remainder}` : `${minutes}:${remainder}`;
    }

    function updateTime() {
        if (currentTimeLabel) currentTimeLabel.textContent = formatTime(video.currentTime);
        if (durationLabel) durationLabel.textContent = formatTime(video.duration);
        if (seekControl && Number.isFinite(video.duration) && video.duration > 0) {
            seekControl.value = String(Math.round(video.currentTime / video.duration * 1000));
        }
    }

    function updatePlayButton() {
        const button = controls.querySelector('[data-player-action="toggle"]');
        const icon = button?.querySelector('i');
        if (icon) icon.className = video.paused ? 'fas fa-play' : 'fas fa-pause';
        if (button) button.setAttribute('aria-label', video.paused ? 'Play' : 'Pause');
    }

    function updateVolume() {
        const button = controls.querySelector('[data-player-action="mute"]');
        const icon = button?.querySelector('i');
        if (icon) icon.className = video.muted || video.volume === 0 ? 'fas fa-volume-xmark' : 'fas fa-volume-high';
        if (button) button.setAttribute('aria-label', video.muted || video.volume === 0 ? 'Unmute' : 'Mute');
        if (volumeControl && Number(volumeControl.value) !== video.volume) volumeControl.value = String(video.volume);
    }

    function showMessage(text) {
        if (message) message.textContent = text;
    }

    function togglePlayback() {
        if (video.paused) {
            video.play().catch(() => showMessage('Playback could not start. Try the native player controls or open the source link.'));
        } else {
            video.pause();
        }
    }

    function skip(seconds) {
        if (Number.isFinite(video.duration)) {
            video.currentTime = Math.max(0, Math.min(video.duration, video.currentTime + seconds));
        }
    }

    function toggleCaptions() {
        const tracks = Array.from(video.textTracks);
        if (!tracks.length) {
            showMessage('No subtitles are available for this video.');
            return;
        }
        const enabled = tracks.some(track => track.mode === 'showing');
        tracks.forEach(track => { track.mode = enabled ? 'disabled' : 'showing'; });
        controls.querySelector('[data-player-action="captions"]')?.setAttribute('aria-pressed', String(!enabled));
        showMessage(enabled ? 'Subtitles off' : 'Subtitles on');
    }

    function toggleFullscreen() {
        const action = document.fullscreenElement
            ? document.exitFullscreen()
            : shell.requestFullscreen?.();
        if (action?.catch) action.catch(() => showMessage('Fullscreen is unavailable in this browser.'));
    }

    async function togglePictureInPicture() {
        try {
            if (document.pictureInPictureElement) {
                await document.exitPictureInPicture();
            } else if (document.pictureInPictureEnabled && video.requestPictureInPicture) {
                await video.requestPictureInPicture();
            } else {
                showMessage('Picture in picture is not supported by this browser.');
            }
        } catch {
            showMessage('Picture in picture could not be started.');
        }
    }

    controls.addEventListener('click', event => {
        const button = event.target.closest('[data-player-action]');
        if (!button) return;
        showMessage('');
        switch (button.dataset.playerAction) {
            case 'toggle':
                togglePlayback();
                break;
            case 'seek-back':
                skip(-10);
                break;
            case 'seek-forward':
                skip(10);
                break;
            case 'mute':
                video.muted = !video.muted;
                updateVolume();
                break;
            case 'loop':
                video.loop = !video.loop;
                button.setAttribute('aria-pressed', String(video.loop));
                button.setAttribute('aria-label', video.loop ? 'Disable loop' : 'Enable loop');
                break;
            case 'captions':
                toggleCaptions();
                break;
            case 'fullscreen':
                toggleFullscreen();
                break;
            case 'pip':
                togglePictureInPicture();
                break;
            case 'copy-link':
                navigator.clipboard.writeText(window.location.href)
                    .then(() => showMessage('Player link copied.'))
                    .catch(() => showMessage('Could not copy the player link.'));
                break;
        }
    });

    seekControl?.addEventListener('input', () => {
        if (Number.isFinite(video.duration)) video.currentTime = Number(seekControl.value) / 1000 * video.duration;
    });
    volumeControl?.addEventListener('input', () => {
        video.volume = Number(volumeControl.value);
        video.muted = video.volume === 0;
        updateVolume();
    });
    speedControl?.addEventListener('change', () => {
        video.playbackRate = Number(speedControl.value);
        showMessage(`Playback speed: ${speedControl.value}x`);
    });
    qualityControl?.addEventListener('change', () => {
        const currentTime = video.currentTime;
        const wasPlaying = !video.paused;
        video.src = qualityControl.value;
        video.load();
        video.addEventListener('loadedmetadata', () => {
            video.currentTime = Math.min(currentTime, video.duration || currentTime);
            if (wasPlaying) video.play().catch(() => showMessage('The selected quality could not be played.'));
        }, { once: true });
    });

    video.addEventListener('timeupdate', updateTime);
    video.addEventListener('loadedmetadata', updateTime);
    video.addEventListener('durationchange', updateTime);
    video.addEventListener('play', updatePlayButton);
    video.addEventListener('pause', updatePlayButton);
    video.addEventListener('volumechange', updateVolume);
    video.addEventListener('error', () => showMessage('This video format could not be played in the browser. Try opening or downloading the source.'));
    video.addEventListener('canplay', () => showMessage(''));

    document.addEventListener('keydown', event => {
        if (event.altKey || event.ctrlKey || event.metaKey || event.target.closest('input, textarea, select, button, a, [contenteditable="true"]')) return;
        switch (event.key.toLowerCase()) {
            case ' ':
                event.preventDefault();
                togglePlayback();
                break;
            case 'arrowleft':
                event.preventDefault();
                skip(-10);
                break;
            case 'arrowright':
                event.preventDefault();
                skip(10);
                break;
            case 'arrowup':
                event.preventDefault();
                video.volume = Math.min(1, video.volume + 0.05);
                video.muted = false;
                break;
            case 'arrowdown':
                event.preventDefault();
                video.volume = Math.max(0, video.volume - 0.05);
                break;
            case 'f':
                toggleFullscreen();
                break;
            case 'm':
                video.muted = !video.muted;
                break;
            case 'c':
                toggleCaptions();
                break;
            case 'l':
                controls.querySelector('[data-player-action="loop"]')?.click();
                break;
        }
    });

    if (video.readyState >= HTMLMediaElement.HAVE_METADATA) updateTime();
    updatePlayButton();
    updateVolume();
})();
