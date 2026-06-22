(() => {
    const imageUploadSettings = {
        maxDimension: 1920,
        jpegQuality: 0.75,
    };

    const decorateViewerTrigger = (image) => {
        if (!(image instanceof HTMLImageElement)) return;
        image.setAttribute("data-image-viewer-trigger", "");
        if (!image.hasAttribute("tabindex")) image.tabIndex = 0;
        if (!image.hasAttribute("role")) image.setAttribute("role", "button");
    };

    const canRewriteFileInput = () => {
        try {
            return typeof DataTransfer === "function";
        } catch {
            return false;
        }
    };

    const setFormProcessing = (form, isProcessing) => {
        if (!(form instanceof HTMLFormElement)) return;
        form.dataset.uploadProcessing = isProcessing ? "true" : "false";
        form.querySelectorAll("button[type='submit']").forEach((button) => {
            if (button instanceof HTMLButtonElement) button.disabled = isProcessing;
        });
    };

    const blobToImage = (blob) =>
        new Promise((resolve, reject) => {
            const image = new Image();
            const objectUrl = URL.createObjectURL(blob);
            image.onload = () => {
                URL.revokeObjectURL(objectUrl);
                resolve(image);
            };
            image.onerror = () => {
                URL.revokeObjectURL(objectUrl);
                reject(new Error("Could not read selected image."));
            };
            image.src = objectUrl;
        });

    const resizedImageFile = async (file) => {
        if (!(file instanceof File) || !file.type.startsWith("image/")) return file;

        const image = await blobToImage(file);
        const largestSide = Math.max(image.naturalWidth, image.naturalHeight);
        const scale = largestSide > imageUploadSettings.maxDimension
            ? imageUploadSettings.maxDimension / largestSide
            : 1;
        const width = Math.max(1, Math.round(image.naturalWidth * scale));
        const height = Math.max(1, Math.round(image.naturalHeight * scale));

        const canvas = document.createElement("canvas");
        canvas.width = width;
        canvas.height = height;
        const context = canvas.getContext("2d");
        if (!context) return file;

        context.drawImage(image, 0, 0, width, height);
        const blob = await new Promise((resolve) => {
            canvas.toBlob(resolve, "image/jpeg", imageUploadSettings.jpegQuality);
        });
        if (!(blob instanceof Blob)) return file;

        const jpgName = file.name.replace(/\.[^.]+$/, "") || "image";
        return new File([blob], `${jpgName}.jpg`, {
            type: "image/jpeg",
            lastModified: Date.now(),
        });
    };

    const resizeSelectedFiles = async (fileInput) => {
        if (!(fileInput instanceof HTMLInputElement) || !canRewriteFileInput()) return;

        const originalFiles = Array.from(fileInput.files || []);
        if (originalFiles.length === 0) return;

        const form = fileInput.closest("form");
        setFormProcessing(form, true);
        try {
            const transfer = new DataTransfer();
            for (const file of originalFiles) {
                transfer.items.add(await resizedImageFile(file));
            }
            fileInput.files = transfer.files;
        } catch (error) {
            console.error(error);
        } finally {
            setFormProcessing(form, false);
        }
    };

    document.querySelectorAll("form[enctype='multipart/form-data']").forEach((form) => {
        form.addEventListener("submit", (event) => {
            if (form.dataset.uploadProcessing !== "true") return;
            event.preventDefault();
        });
    });

    const notebookInput = document.querySelector("[data-notebook-input]");
    if (notebookInput) {
        const previewTargetId = notebookInput.dataset.previewTarget;
        const previewRoot = previewTargetId ? document.getElementById(previewTargetId) : null;

        notebookInput.addEventListener("change", async () => {
            await resizeSelectedFiles(notebookInput);
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

        photoInput.addEventListener("change", async () => {
            await resizeSelectedFiles(photoInput);
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
