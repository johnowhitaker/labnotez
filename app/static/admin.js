(() => {
    const decorateViewerTrigger = (image) => {
        if (!(image instanceof HTMLImageElement)) return;
        image.setAttribute("data-image-viewer-trigger", "");
        if (!image.hasAttribute("tabindex")) image.tabIndex = 0;
        if (!image.hasAttribute("role")) image.setAttribute("role", "button");
    };

    const notebookInput = document.querySelector("[data-notebook-input]");
    if (notebookInput) {
        const previewTargetId = notebookInput.dataset.previewTarget;
        const previewRoot = previewTargetId ? document.getElementById(previewTargetId) : null;

        notebookInput.addEventListener("change", () => {
            if (!previewRoot) return;
            previewRoot.innerHTML = "";
            const file = notebookInput.files && notebookInput.files[0];
            if (!file) return;

            const objectUrl = URL.createObjectURL(file);
            const figure = document.createElement("figure");
            figure.innerHTML = `
                <img src="${objectUrl}" alt="Notebook preview" data-image-viewer-trigger>
                <figcaption>Selected notebook image</figcaption>
            `;
            decorateViewerTrigger(figure.querySelector("img"));
            previewRoot.appendChild(figure);
        });
    }

    const photoInput = document.querySelector("[data-photo-input]");
    if (photoInput) {
        const previewTargetId = photoInput.dataset.previewTarget;
        const captionName = photoInput.dataset.captionName || "photo_caption";

        const previewRoot = previewTargetId ? document.getElementById(previewTargetId) : null;

        photoInput.addEventListener("change", () => {
            if (!previewRoot) return;

            previewRoot.innerHTML = "";

            const files = Array.from(photoInput.files || []);
            files.forEach((file, index) => {
                const objectUrl = URL.createObjectURL(file);

                const card = document.createElement("article");
                card.className = "new-photo-card";

                const label = document.createElement("label");
                label.className = "new-photo-caption-label";
                label.textContent = `Photo ${index + 1} caption`;
                const input = document.createElement("input");
                input.type = "text";
                input.name = captionName;
                input.placeholder = "Optional caption";
                label.appendChild(input);

                card.innerHTML = `
                    <p class="new-photo-index">Photo ${index + 1}</p>
                    <img src="${objectUrl}" alt="New photo ${index + 1}" data-image-viewer-trigger>
                    <p class="new-photo-name">${file.name}</p>
                `;
                decorateViewerTrigger(card.querySelector("img"));
                card.appendChild(label);
                previewRoot.appendChild(card);
            });
        });
    }

    const textareas = document.querySelectorAll("textarea[data-autosize]");
    textareas.forEach((textarea) => {
        const resize = () => {
            textarea.style.height = "auto";
            textarea.style.height = `${textarea.scrollHeight}px`;
        };
        resize();
        textarea.addEventListener("input", resize);
    });

    const imageViewer = document.querySelector("[data-image-viewer]");
    if (imageViewer) {
        const viewerImage = imageViewer.querySelector("[data-image-viewer-image]");
        const viewerCaption = imageViewer.querySelector("[data-image-viewer-caption]");
        const closeTriggers = imageViewer.querySelectorAll("[data-image-viewer-close]");
        const closeButton = imageViewer.querySelector(".image-viewer-close");
        let restoreFocusTo = null;

        const closeViewer = () => {
            if (imageViewer.hidden) return;
            imageViewer.hidden = true;
            imageViewer.setAttribute("aria-hidden", "true");
            document.body.classList.remove("viewer-open");
            if (viewerImage instanceof HTMLImageElement) {
                viewerImage.src = "";
                viewerImage.alt = "";
            }
            if (viewerCaption instanceof HTMLElement) {
                viewerCaption.textContent = "";
                viewerCaption.hidden = true;
            }
            if (restoreFocusTo instanceof HTMLElement) {
                restoreFocusTo.focus();
            }
            restoreFocusTo = null;
        };

        const openViewer = (sourceImage) => {
            if (!(viewerImage instanceof HTMLImageElement)) return;
            const source = sourceImage.currentSrc || sourceImage.src;
            if (!source) return;

            restoreFocusTo = document.activeElement instanceof HTMLElement ? document.activeElement : null;

            viewerImage.src = source;
            viewerImage.alt = sourceImage.alt || "Expanded image";
            if (viewerCaption instanceof HTMLElement) {
                const caption = sourceImage.closest("figure")?.querySelector("figcaption")?.textContent?.trim() || "";
                viewerCaption.textContent = caption;
                viewerCaption.hidden = !caption;
            }

            imageViewer.hidden = false;
            imageViewer.setAttribute("aria-hidden", "false");
            document.body.classList.add("viewer-open");
            if (closeButton instanceof HTMLElement) {
                closeButton.focus();
            }
        };

        const openFromTarget = (target) => {
            if (!(target instanceof Element)) return;
            if (!imageViewer.hidden) return;
            const trigger = target.closest("img[data-image-viewer-trigger]");
            if (!(trigger instanceof HTMLImageElement)) return;
            openViewer(trigger);
        };

        document.querySelectorAll("img[data-image-viewer-trigger]").forEach((image) => {
            decorateViewerTrigger(image);
        });

        closeTriggers.forEach((trigger) => {
            trigger.addEventListener("click", closeViewer);
        });

        document.addEventListener("click", (event) => {
            openFromTarget(event.target);
        });

        document.addEventListener("keydown", (event) => {
            if (event.key === "Escape" && !imageViewer.hidden) {
                event.preventDefault();
                closeViewer();
                return;
            }

            if (event.key !== "Enter" && event.key !== " ") return;
            const target = event.target;
            if (!(target instanceof Element)) return;
            const trigger = target.closest("img[data-image-viewer-trigger]");
            if (!(trigger instanceof HTMLImageElement)) return;
            event.preventDefault();
            openViewer(trigger);
        });
    }
})();
