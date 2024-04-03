// File: Lib.js

$(document).ready(function () {

    // remove pull validation errors div
    $('#pull-validation-errors').empty();

    // Adds actions to all teh container buttons
    ['delete', 'start', 'stop', 'kill', 'restart', 'pause', 'resume'].forEach(action => {
        $(`#btn-${action}`).click(function () {
            performActionContainer(action, `btn-${action}`);
        });
    });
    // add actions to all the image section buttons
    ['delete', 'pull'].forEach(action => {
        $(`#${action}-img-btn`).click(function () {
            performActionImage(action, `${action}-img-btn`);
        });
    });
    // add actions to all the compose file buttons
    ['down', 'up', 'delete'].forEach(action => {
        // pass down the click event, to modify the button
        $(document).on('click', `[id^="${action}-compose-btn-"]`, function (event) {
            const projectName = this.id.replace(`${action}-compose-btn-`, '');
            performActionCompose(action, projectName, event);
        });
    });

    // table spinners
    $("#containers-loading").show();
    $("#images-loading").show();

    // Get event sources
    var containerListSource = null;
    function initContainerListES() {
        if (containerListSource == null || containerListSource.readyState == 2) {
            containerListSource = new EventSource('http://localhost:5002/api/streams/containerlist');
            containerListSource.onerror = function (event) {
                if (containerListSource.readyState == 2) {
                    // retry connection to ES
                    setTimeout(initContainerListES, 5000);
                }
            }
            var containersTbody = $("#containers-tbody");
            var previousStateContainers = {};
            var firstLoadContainerList = true;
            containerListSource.onmessage = function (event) {
                var data = JSON.parse(event.data);
                // keep track of containerIds in the incoming data stream
                var containerIds = new Set(data.map(container => container.ID));
                // remove any rows with IDs not in the set
                containersTbody.find('tr').each(function () {
                    var tr = $(this);
                    var id = tr.attr('id').substring(4);  // remove 'row-' prefix
                    if (!containerIds.has(id)) {
                        tr.remove();
                    }
                });
                $.each(data, function (i, container) {
                    var tr = containersTbody.find('#row-' + container.ID);
                    if (!tr.length) {
                        // If the row does not exist, create it
                        tr = $("<tr>").attr('id', 'row-' + container.ID);
                        tr.append($("<td>").html('<input type="checkbox" class="tr-container-checkbox" value="' + container.ID + '" name="container"> <span class="spinner-border spinner-border-sm text-warning d-none" role="status" aria-hidden="true"></span>'));
                        tr.append($("<td>").attr('id', 'name-' + container.ID));
                        tr.append($("<td>").attr('id', 'id-' + container.ID));
                        tr.append($("<td>").attr('id', 'state-' + container.ID));
                        tr.append($("<td>").attr('id', 'status-' + container.ID));
                        tr.append($("<td>").attr('id', 'image-' + container.ID));
                        tr.append($("<td>").attr('id', 'port-' + container.ID));
                        tr.append($("<td>").html('<button class="transparent-btn" onclick="getInfo(\'' + container.ID + '\')"><i class="bi bi-info-circle text-primary"></i></button>'));
                        // first load, all rows are new so append in order the data was sent
                        // if its the first load, append everything
                        // if its a newly created container, will have to prepend
                        if (firstLoadContainerList) {
                            containersTbody.append(tr);
                        } else {
                            containersTbody.prepend(tr);
                        }
                    }

                    // Define the attributes to be updated
                    const attributes = ['Names', 'ID', 'State', 'Status', 'Image', 'Ports'];
                    attributes.forEach(attr => {
                        // If the attribute has changed
                        if (previousStateContainers[container.ID]?.[attr] !== container[attr]) {
                            switch (attr) {
                                case 'Names':
                                    $(`#name-${container.ID}`).text(container.Names[0].substring(1));
                                    break;
                                case 'ID':
                                    $(`#id-${container.ID}`).text(container.ID.substring(0, 12));
                                    break;
                                case 'State':
                                    $(`#state-${container.ID}`).html(`<span class="badge bg-${getStatusClass(container.State)}">${container.State}</span>`);
                                    break;
                                case 'Status':
                                    $(`#status-${container.ID}`).html(`<span class="badge bg-${getStatusClass(container.Status)}">${container.Status}</span>`);
                                    break;
                                case 'Image':
                                    $(`#image-${container.ID}`).text(container.Image);
                                    break;
                                case 'Ports':
                                    $(`#port-${container.ID}`).html(getPortBindings(container.Ports));
                                    break;
                            }
                        }
                    });

                    // Store the current state of the container for the next update
                    previousStateContainers[container.ID] = container;
                });
                if (firstLoadContainerList) {
                    firstLoadContainerList = false;
                }

                $("#containers-loading").hide();
            };
        }
    }
    initContainerListES();

    var messagesSource = null;
    function initMessageES() {
        if (messagesSource == null || messagesSource.readyState == 2) {
            messagesSource = new EventSource('http://localhost:5002/api/streams/servermessages');
            messagesSource.onerror = function (event) {
                if (messagesSource.readyState == 2) {
                    // retry connection to ES
                    setTimeout(initMessageES, 5000);
                }
            }
        }
        messagesSource.onmessage = function (event) {
            var data = JSON.parse(event.data);
            let icon;
            let toastHeaderBgColor;
            const uniqueId = 'toast' + Date.now();
            const timeSent = new Date(data.timeSent * 1000);
            const now = new Date();
            const diffInMilliseconds = now - timeSent;
            const diffInMinutes = Math.floor(diffInMilliseconds / 1000 / 60);
            // if data.category is success use success, error uses danger
            switch (data.category.toLowerCase()) {
                case 'success':
                    toastHeaderBgColor = 'success';
                    icon = `<i class="fa-solid fa-circle-check text-light"></i>`;
                    break;
                case 'error':
                    toastHeaderBgColor = 'danger';
                    icon = `<i class="fa-solid fa-circle-exclamation  text-light"></i>`;
                    break;
            }
            $('#toast-container').append(`
              <div id="${uniqueId}" class="toast" role="alert" aria-live="assertive" aria-atomic="true">
                <div class="toast-header d-flex align-items-center bg-${toastHeaderBgColor}">
                    <span style="margin-right: 10px">${icon}</span>
                    <strong class="me-auto  text-light">${data.category}</strong>
                    <small class="text-light">${diffInMinutes} mins ago</small>
                    <div data-bs-theme="dark">
                        <button type="button" class="btn-close" data-bs-dismiss="toast" aria-label="Close"></button>
                    </div>
                </div>
                <div class="toast-body">
                  ${data.text}
                </div>
              </div>
            </div>
          `);
            // Initialize the toast
            $('#' + uniqueId).toast('show');
        };
    }
    initMessageES();

    var imageListSource = null;
    function initImageListES() {
        if (imageListSource == null || imageListSource.readyState == 2) {
            imageListSource = new EventSource('http://localhost:5002/api/streams/imagelist');
            imageListSource.onerror = function (event) {
                if (imageListSource.readyState == 2) {
                    // retry connection to ES
                    setTimeout(initImageListES, 5000);
                }
            }
        }
        // handle new messages from image list stream
        let previousStateImages = {};
        let firstLoadImageList = true;
        const imagesTbody = $("#images-tbody");
        imageListSource.onmessage = function (event) {
            const data = JSON.parse(event.data);
            // Created - timestamp
            // Id.split(":")[1].substring(12) - gets short id, otherwise complete hash
            // RepoTags[0] - name of image
            // Size (bytes) - convert to mb
            // RepoTags[0].split(":")[1] gets tag of image
            // Labels{} - holds compose information
            // keep track of containerIds in the incoming data stream
            // getting short id
            const imageIds = new Set(data.map(image => image.ID));
            // remove any rows with IDs not in the set
            imagesTbody.find('tr').each(function () {
                const tr = $(this);
                const id = tr.attr('id').substring(4);  // remove 'row-' prefix
                if (!imageIds.has(id)) {
                    tr.remove();
                }
            });
            $.each(data, function (i, image) {
                let tr = imagesTbody.find('#row-' + image.ID);
                if (!tr.length) {
                    // If the row does not exist, create it
                    tr = $("<tr>").attr('id', 'row-' + image.ID);
                    tr.append($("<td>").html('<input type="checkbox" class="tr-image-checkbox" value="' + image.ID + '" name="container"> <span class="spinner-border spinner-border-sm text-warning d-none" role="status" aria-hidden="true"></span>'));
                    tr.append($("<td>").attr('id', 'name-' + image.ID));
                    tr.append($("<td>").attr('id', 'tag-' + image.ID));
                    tr.append($("<td>").attr('id', 'created-date-' + image.ID));
                    tr.append($("<td>").attr('id', 'size-' + image.ID));
                    tr.append($("<td>").attr('id', 'used-by-' + image.ID));
                    // first load, all rows are new so append in order the data was sent
                    // if its the first load, append everything
                    // if its a newly created container, will have to prepend
                    if (firstLoadImageList) {
                        imagesTbody.append(tr);
                    } else {
                        imagesTbody.prepend(tr);
                    }
                }

                // Define the attributes to be updated
                const attributes = ['Name', 'Tag', 'Created', 'NumContainers', 'Size'];
                attributes.forEach(attr => {
                    // If the attribute has changed
                    if (previousStateImages[image.ID]?.[attr] !== image[attr]) {
                        switch (attr) {
                            case 'Name':
                                let formattedName = image.Name.split(':')[0];
                                $(`#name-${image.ID}`).text(formattedName);
                                break;
                            case 'Tag':
                                $(`#tag-${image.ID}`).html(`<span class="badge bg-secondary">${image.Tag}</span>`);
                                break;
                            case 'Created':
                                const createdTimeStamp = new Date(image.Created * 1000);
                                $(`#created-date-${image.ID}`).html(`<span>${createdTimeStamp.toLocaleDateString()}</span>`);
                                break;
                            case 'NumContainers':
                                $(`#used-by-${image.ID}`).html(`<span style="padding-left: 25px">${image.NumContainers}</span>`);
                                break;
                            case 'Size':
                                // convert bytes to mb and gb if necessary
                                const sizeInBytes = image.Size;
                                const sizeInMb = sizeInBytes / 1048576
                                const sizeInGb = sizeInMb / 1024
                                let displaySize;
                                if (sizeInGb < 1) {
                                    displaySize = `${sizeInMb.toFixed(2)} MB`;
                                } else {
                                    displaySize = `${sizeInGb.toFixed(2)} GB`;
                                }
                                $(`#size-${image.ID}`).text(displaySize);
                                break;
                        }
                    }
                });

                // Store the current state of the container for the next update
                previousStateImages[image.ID] = image;
            });
            if (firstLoadImageList) {
                firstLoadImageList = false;
            }

            $("#images-loading").hide();
        };
    }
    initImageListES();



    // handle file uploading
    $('#upload-compose-btn').click(function (e) {
        // get projectName
        const projectName = $('#projectName').val();
        // get yaml contents
        const yamlContents = $('#yamlContents').val();

        // alert if fields aren't filled in
        if (!projectName || !yamlContents) {
            alert('Please fill out required fields.');
            return;
        }

        // disable button and show spinner
        $(this).addClass('disabled');
        $(this).find('.spinner-border').toggleClass('d-none');

        $.ajax({
            url: 'http://localhost:5002/api/compose/upload',
            type: 'POST',
            data: JSON.stringify({
                "projectName": projectName,
                "yamlContents": yamlContents,
            }),
            processData: false,  // tell jQuery not to process the data
            contentType: false,  // tell jQuery not to set contentType
            success: function (data) {
                $('#upload-compose-btn').removeClass('disabled');
                $('#upload-compose-btn').find('.spinner-border').toggleClass('d-none');
                // clear projectName input and textarea
                $('#projectName').val('');
                $('#yamlContents').val('');
                // hide modal
                $('#composeModal').modal('hide');
            }
        });
    });

    // retrieve composefiles eventsource
    var composeFilesSource = null;
    let composeFilesState = new Set();
    function initComposeFilesSource() {
        if (composeFilesSource == null || composeFilesSource.readyState == 2) {
            composeFilesSource = new EventSource('http://localhost:5002/api/streams/composefiles');
            composeFilesSource.onerror = function (event) {
                if (composeFilesSource.readyState == 2) {
                    // retry connection to ES
                    setTimeout(composeFilesSource, 5000);
                }
            }
        }
        composeFilesSource.onmessage = function (event) {
            // event.data.files -> list of file names within /composefiles directory
            if (event.data.trim() === "") {
                // data hasnt changed, recieved heartbeat from server so return
                return;
            }
            // if event.data['files'] doesnt have what is on the screen, remove it
            const data = JSON.parse(event.data);
            console.log(data);
            console.log("Tracked state: " + composeFilesState);
            data.files.forEach(fileName => {
                if (!composeFilesState.has(fileName)) {
                    composeFilesState.add(fileName);
                    const newCard = `<div class="compose-file d-flex justify-content-center align-items-center" id="${fileName}">
                            <p>${fileName}</p>
                            <div
                                class="hover-div d-flex flex-column justify-content-center align-items-center">
                                <button class="btn btn-primary mb-2" id="up-compose-btn-${fileName}">
                                    <span class="spinner-border spinner-border-sm d-none" aria-hidden="true"></span>
                                    <span class="visually-hidden" role="status">Loading...</span>
                                    Up
                                </button>
                                <button class="btn btn-danger mb-2" id="down-compose-btn-${fileName}">
                                    <span class="spinner-border spinner-border-sm d-none" aria-hidden="true"></span>
                                    <span class="visually-hidden" role="status">Loading...</span>
                                    Down
                                </button>
                                <button class="btn btn-secondary" id="delete-compose-btn-${fileName}">
                                    <span class="spinner-border spinner-border-sm d-none" aria-hidden="true"></span>
                                    <span class="visually-hidden" role="status">Loading...</span>
                                    <i class="bi bi-trash-fill"></i>
                                </button>
                            </div>
                        </div>`;
                    $('#compose-files-list').append(newCard);
                }
            });

            // Remove cards that are not in the current files list
            $('.compose-file').each(function () {
                const fileName = this.id;
                if (!data.files.includes(fileName)) {
                    $(this).remove();
                    composeFilesState.delete(fileName);
                }
            });
        }
    }
    initComposeFilesSource();

    // Function to close EventSource connections
    // close() calls the call_on_close in server and unsubscribes from topic
    function closeEventSources() {
        containerListSource.close();
        messagesSource.close();
        imageListSource.close();
        composeFilesSource.close();
    }

    // Close connections when the page is refreshed or closed
    $(window).on('beforeunload', function () {
        closeEventSources();
    });

    // handle prune selecting check boxes
    $('#all-prune-check').change(function () {
        if (this.checked) {
            // Disable individual checkboxes if "All" is checked
            $('#individual-prune-selects input[type="checkbox"]').each(function () {
                $(this).prop('disabled', true);
                $(this).prop('checked', true);
            });
        } else {
            // Enable individual checkboxes if "All" is unchecked
            $('#individual-prune-selects input[type="checkbox"]').each(function () {
                $(this).prop('disabled', false);
                $(this).prop('checked', false);
            });
        }
    });

    // handle prune check box
    $('#btncheck1').change(function () {
        $('#confirm-prune').toggleClass('disabled');
    });

    // handle prune button click
    $('#confirm-prune').on('click', function () {
        // hide prune modal
        $("#pruneModal").modal('hide');
        // uncheck box for next opening of modal
        $("#btncheck1").prop('checked', false);
        $("#confirm-prune").toggleClass('disabled');
        // get data
        let checkedToPrune = []
        $('#individual-prune-selects input[type="checkbox"]').each(function () {
            if ($(this).prop('checked') == true) {
                checkedToPrune.push($(this).val());
            }
        });
        // close modal
        $('#pruneModal').modal('hide');
        // disable prune button
        $('#prune-btn').addClass('disabled');
        // hide icon
        $('#prune-icon').addClass('d-none');
        // show spinner
        $('#prune-spinner').toggleClass('d-none');
        $.ajax({
            url: 'http://localhost:5002/api/system/prune',
            type: 'POST',
            contentType: 'application/json',
            data: JSON.stringify({
                'objectsToPrune': checkedToPrune
            }),
            success: function (result) {
                // enable prune button
                $('#prune-btn').removeClass('disabled');
                // show icon
                $('#prune-icon').removeClass('d-none');
                // hide spinner
                $('#prune-spinner').toggleClass('d-none');
                // clear checkboxes
                $('#individual-prune-selects input[type="checkbox"]').each(function () {
                    $(this).prop('checked', false);
                    $(this).prop('disabled', false);
                });
                $('#all-prune-check').prop('checked', false);
            },
            error: function (result) {
                console.error(result);
            }
        });
    })

    // handle select all checkbox change
    $('#select-all').change(function () {
        // select all checkboxes with class of tr-checkbox and make them selected
        $('.tr-container-checkbox').prop('checked', this.checked);
        // enable/disable buttons
        if (this.checked) {
            $('#btn-stop, #btn-kill, #btn-restart, #btn-pause, #btn-delete, #btn-resume, #btn-start').removeClass('disabled');
        } else {
            // If no checkboxes are checked, disable all buttons
            $('#btn-stop, #btn-kill, #btn-restart, #btn-pause, #btn-delete, #btn-resume, #btn-start').addClass('disabled');
        }
    });
    $('#select-all-image').change(function () {
        // select all checkboxes with class of tr-checkbox and make them selected
        $('.tr-image-checkbox').prop('checked', this.checked);
        // enable/disable buttons
        if (this.checked) {
            $('#delete-img-btn').removeClass('disabled');
        } else {
            // If no checkboxes are checked, disable all buttons
            $('#delete-img-btn').addClass('disabled');
        }
    });
});

// Enables container action buttons after checkbox input
$(document).on('change', '.tr-container-checkbox', function () {
    const checkedCount = $('.tr-container-checkbox:checked').length;
    const buttonSelector = '#btn-stop, #btn-kill, #btn-restart, #btn-pause, #btn-delete, #btn-resume, #btn-start';

    $(buttonSelector).toggleClass('disabled', checkedCount === 0);
});

// Enables image action buttons after checkbox input
$(document).on('change', '.tr-image-checkbox', function () {
    const checkedCount = $('.tr-image-checkbox:checked').length;
    const buttonSelector = '#delete-img-btn';

    $(buttonSelector).toggleClass('disabled', checkedCount === 0);
});