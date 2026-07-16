// Note: Most of this JS code is AI-generated.

import Uppy from '@uppy/core'
import Dashboard from '@uppy/dashboard'
import Webcam from '@uppy/webcam'
import AwsS3 from '@uppy/aws-s3'
import ImageEditor from '@uppy/image-editor'

import '@uppy/core/css/style.css'
import '@uppy/webcam/css/style.css'
import '@uppy/dashboard/css/style.css'
import '@uppy/image-editor/css/style.min.css'


function getCsrfToken() {
    const element = document.querySelector('meta[name="csrf-token"]')

    return element
        ? element.getAttribute('content')
        : ''
}


function parseBoolean(value, fallback = false) {
    if (
        value === undefined ||
        value === null ||
        value === ''
    ) {
        return fallback
    }

    return value !== 'false'
}


function parseNumber(value, fallback) {
    const parsed = Number(value)

    return Number.isFinite(parsed)
        ? parsed
        : fallback
}


function getExistingFileIds(input) {
    if (!input || !input.value) {
        return []
    }

    try {
        const parsed = JSON.parse(input.value)

        if (Array.isArray(parsed)) {
            return parsed
        }

        if (
            typeof parsed === 'string' &&
            parsed.trim() !== ''
        ) {
            return [parsed]
        }

        return []
    } catch {
        return input.value
            ? [input.value]
            : []
    }
}


function getHiddenInput(form, inputName) {
    const escapedName = CSS.escape(inputName)

    let input = form.querySelector(
        `input[data-uploaded-file-input="true"][name="${escapedName}"]`
    )

    if (input) {
        return input
    }

    input = form.querySelector(
        `input[type="hidden"][name="${escapedName}"]`
    )

    if (input) {
        input.dataset.uploadedFileInput = 'true'
        return input
    }

    return null
}


function createHiddenInput(
    form,
    inputName,
    initialValue = ''
) {
    const input = document.createElement('input')

    input.type = 'hidden'
    input.name = inputName
    input.value = initialValue
    input.dataset.uploadedFileInput = 'true'

    form.appendChild(input)

    return input
}


function setSingleHiddenFileInput(
    form,
    fileId,
    inputName
) {
    let input = getHiddenInput(form, inputName)

    if (!input) {
        input = createHiddenInput(
            form,
            inputName
        )
    }

    input.value = fileId
}


function addMultiHiddenFileInput(
    form,
    fileId,
    inputName
) {
    let input = getHiddenInput(form, inputName)

    if (!input) {
        input = createHiddenInput(
            form,
            inputName,
            '[]'
        )
    }

    const existingIds = getExistingFileIds(input)

    if (!existingIds.includes(fileId)) {
        existingIds.push(fileId)
    }

    input.value = JSON.stringify(existingIds)
}


function addHiddenFileInput(
    form,
    fileId,
    inputName,
    multiple
) {
    if (multiple) {
        addMultiHiddenFileInput(
            form,
            fileId,
            inputName
        )

        return
    }

    setSingleHiddenFileInput(
        form,
        fileId,
        inputName
    )
}


function removeHiddenFileInput(
    form,
    fileId,
    inputName,
    multiple
) {
    const input = getHiddenInput(
        form,
        inputName
    )

    if (!input) {
        return
    }

    if (!multiple) {
        if (input.value === fileId) {
            input.value = ''
        }

        return
    }

    const existingIds = getExistingFileIds(input)

    const updatedIds = existingIds.filter(
        (id) => id !== fileId
    )

    input.value = JSON.stringify(updatedIds)
}


function getUploaderConfig(element) {
    return {
        context:
            element.dataset.context ||
            'general',

        inputName:
            element.dataset.inputName ||
            'uploaded_file_ids',

        multiple: parseBoolean(
            element.dataset.multiple,
            true
        ),

        maxFileSize: parseNumber(
            element.dataset.maxFileSize,
            25 * 1024 * 1024
        ),

        autoProceed: parseBoolean(
            element.dataset.autoProceed,
            false
        ),

        requireUploadedFiles: parseBoolean(
            element.dataset.requireUploadedFiles,
            true
        ),

        debug: parseBoolean(
            element.dataset.debug,
            false
        ),
    }
}


function getTargetForm(element) {
    const formId = element.dataset.form

    if (formId) {
        const form = document.getElementById(formId)

        if (!form) {
            console.warn(
                `Uploader form target not found: #${formId}`
            )

            return null
        }

        return form
    }

    return element.closest('form')
}


function getFormErrorElement(form) {
    return form.querySelector(
        '#upload-form-error'
    )
}


function showFormError(form, message) {
    const errorElement =
        getFormErrorElement(form)

    if (!errorElement) {
        return
    }

    const messageElement =
        errorElement.querySelector('span')

    if (messageElement) {
        messageElement.textContent = message
    }

    errorElement.classList.remove('hidden')
}


function clearFormError(form) {
    const errorElement =
        getFormErrorElement(form)

    if (!errorElement) {
        return
    }

    const messageElement =
        errorElement.querySelector('span')

    if (messageElement) {
        messageElement.textContent = ''
    }

    errorElement.classList.add('hidden')
}


function createUploader(element) {
    const form = getTargetForm(element)

    if (!form) {
        console.warn(
            'Uploader must be placed inside a form or provide data-form="form_id".'
        )

        return null
    }

    const config = getUploaderConfig(element)

    const uppy = new Uppy({
        debug: config.debug,
        autoProceed: config.autoProceed,

        restrictions: {
            maxFileSize: config.maxFileSize,
            maxNumberOfFiles:
                config.multiple
                    ? null
                    : 1,
        },
    })

    uppy.use(Webcam)

    uppy.use(ImageEditor)

    uppy.use(Dashboard, {
        inline: true,
        target: element,
        plugins: [
            'Webcam',
            'ImageEditor',
        ],
        proudlyDisplayPoweredByUppy: false,
    })

    uppy.use(AwsS3, {
        shouldUseMultipart: false,

        async getUploadParameters(file) {
            const contentType =
                file.type ||
                'application/octet-stream'

            const response = await fetch(
                '/api/v1/uploads/presign',
                {
                    method: 'POST',

                    headers: {
                        'Content-Type':
                            'application/json',

                        'X-CSRFToken':
                            getCsrfToken(),
                    },

                    body: JSON.stringify({
                        filename: file.name,
                        content_type: contentType,
                        size_bytes: file.size,
                        context: config.context,
                    }),
                }
            )

            if (!response.ok) {
                const error = await response
                    .json()
                    .catch(() => ({}))

                throw new Error(
                    error.message ||
                    error.error ||
                    'Could not prepare upload.'
                )
            }

            const data = await response.json()

            uppy.setFileMeta(file.id, {
                uploaded_file_id:
                data.file_id,

                object_key:
                data.object_key,
            })

            return {
                method: 'PUT',
                url: data.upload_url,

                headers: {
                    'Content-Type':
                        data.content_type ||
                        contentType,
                },
            }
        },
    })

    uppy.on(
        'upload-success',
        (file, response) => {
            const fileId =
                file.meta.uploaded_file_id

            if (!fileId) {
                console.warn(
                    'Upload succeeded, but no uploaded_file_id was returned.',
                    {
                        file,
                        response,
                    }
                )

                return
            }

            addHiddenFileInput(
                form,
                fileId,
                config.inputName,
                config.multiple
            )

            clearFormError(form)
        }
    )

    uppy.on(
        'file-removed',
        (file) => {
            const fileId =
                file.meta.uploaded_file_id

            if (!fileId) {
                return
            }

            removeHiddenFileInput(
                form,
                fileId,
                config.inputName,
                config.multiple
            )
        }
    )

    uppy.on(
        'upload-error',
        (file, error, response) => {
            console.error(
                'Upload failed:',
                {
                    filename: file?.name,
                    contentType: file?.type,
                    error,
                    response,
                }
            )

            showFormError(
                form,
                error?.message ||
                `Could not upload ${file?.name || 'the selected file'}.`
            )
        }
    )

    /*
     * This handler does not upload anything.
     *
     * It only stops submission when:
     * 1. Files are currently uploading.
     * 2. Selected files have not been uploaded.
     * 3. No completed file IDs are available.
     *
     * When validation passes, the normal browser form
     * submission continues without interference.
     */
    form.addEventListener('submit', (event) => {
        clearFormError(form)

        const files = uppy.getFiles()

        const uploadingFiles = files.filter(
            (file) =>
                file.progress?.uploadStarted &&
                !file.progress?.uploadComplete
        )

        /*
         * Always prevent submission while a selected file is actively
         * uploading. Otherwise, the form could submit without its file ID.
         */
        if (uploadingFiles.length > 0) {
            event.preventDefault()

            showFormError(
                form,
                'Wait for all files to finish uploading before submitting the form.'
            )

            return
        }

        const unuploadedFiles = files.filter(
            (file) => !file.progress?.uploadComplete
        )

        /*
         * A selected file must still be uploaded before submission,
         * even when an uploaded file is not required.
         *
         * The bypass only permits submitting with no selected file.
         */
        if (unuploadedFiles.length > 0) {
            event.preventDefault()

            showFormError(
                form,
                'Upload the selected files before submitting the form.'
            )

            return
        }

        /*
         * Some forms, such as profile-picture forms, may submit without
         * a newly uploaded file. This permits actions such as removing
         * the existing profile picture.
         */
        if (!config.requireUploadedFiles) {
            return
        }

        const hiddenInput = getHiddenInput(
            form,
            config.inputName
        )

        const uploadedFileIds = getExistingFileIds(
            hiddenInput
        )

        if (uploadedFileIds.length === 0) {
            event.preventDefault()

            showFormError(
                form,
                'Upload at least one file before submitting the form.'
            )
        }
    })

    element.uppy = uppy

    return uppy
}


function initializeUploaders() {
    document
        .querySelectorAll(
            '[data-uppy-uploader]'
        )
        .forEach((element) => {
            if (element.uppy) {
                return
            }

            createUploader(element)
        })
}


if (document.readyState === 'loading') {
    document.addEventListener(
        'DOMContentLoaded',
        initializeUploaders
    )
} else {
    initializeUploaders()
}