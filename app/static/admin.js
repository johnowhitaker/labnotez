(() => {
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
                <img src="${objectUrl}" alt="Notebook preview">
                <figcaption>Selected notebook image</figcaption>
            `;
            previewRoot.appendChild(figure);
        });
    }

    const photoInput = document.querySelector("[data-photo-input]");
    if (photoInput) {
        const previewTargetId = photoInput.dataset.previewTarget;
        const captionTargetId = photoInput.dataset.captionTarget;
        const captionName = photoInput.dataset.captionName || "photo_caption";

        const previewRoot = previewTargetId ? document.getElementById(previewTargetId) : null;
        const captionRoot = captionTargetId ? document.getElementById(captionTargetId) : null;

        photoInput.addEventListener("change", () => {
            if (!previewRoot || !captionRoot) return;

            previewRoot.innerHTML = "";
            captionRoot.innerHTML = "";

            const files = Array.from(photoInput.files || []);
            files.forEach((file, index) => {
                const objectUrl = URL.createObjectURL(file);

                const figure = document.createElement("figure");
                figure.innerHTML = `
                    <img src="${objectUrl}" alt="New photo ${index + 1}">
                    <figcaption>${file.name}</figcaption>
                `;
                previewRoot.appendChild(figure);

                const label = document.createElement("label");
                label.textContent = `Caption for photo ${index + 1}`;
                const input = document.createElement("input");
                input.type = "text";
                input.name = captionName;
                input.placeholder = "Optional caption";
                label.appendChild(input);
                captionRoot.appendChild(label);
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
})();
