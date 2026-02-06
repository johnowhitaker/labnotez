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
                    <img src="${objectUrl}" alt="New photo ${index + 1}">
                    <p class="new-photo-name">${file.name}</p>
                `;
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
})();
