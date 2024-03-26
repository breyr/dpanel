// File: Lib.js

$(document).ready(function () {

    // Adds actions to all teh container buttons
    ['delete', 'start', 'stop', 'kill', 'restart', 'pause', 'resume'].forEach(action => {
        $(`#btn-${action}`).click(function () {
            performAction(action, `btn-${action}`);
        });
    });

    $("#loading").show();

    // Get event sources
    var homepageSource = new EventSource('http://localhost:5002/api/streams/containerlist');
    var messagesSource = new EventSource('http://localhost:5002/api/streams/servermessages');

    // Function to close EventSource connections
    // close() calls the call_on_close in server and unsubscribes from topic
    function closeEventSources() {
        homepageSource.close();
        messagesSource.close();
    }

    // Close connections when the page is refreshed or closed
    $(window).on('beforeunload', function () {
        closeEventSources();
    });

    var tbody = $("table tbody");
    var previousState = {};
    var firstLoad = true;
    homepageSource.onmessage = function (event) {
        var data = JSON.parse(event.data);
        // keep track of containerIds in the incoming data stream
        var containerIds = new Set(data.map(container => container.ID));
        // remove any rows with IDs not in the set
        tbody.find('tr').each(function () {
            var tr = $(this);
            var id = tr.attr('id').substring(4);  // remove 'row-' prefix
            if (!containerIds.has(id)) {
                tr.remove();
            }
        });
        $.each(data, function (i, container) {
            var tr = tbody.find('#row-' + container.ID);
            if (!tr.length) {
                // If the row does not exist, create it
                tr = $("<tr>").attr('id', 'row-' + container.ID);
                tr.append($("<td>").html('<input type="checkbox" class="tr-checkbox" value="' + container.ID + '" name="container"> <span class="spinner-border spinner-border-sm text-warning d-none" role="status" aria-hidden="true"></span>'));
                tr.append($("<td>").attr('id', 'name-' + container.ID));
                tr.append($("<td>").attr('id', 'id-' + container.ID));
                tr.append($("<td>").attr('id', 'state-' + container.ID));
                tr.append($("<td>").attr('id', 'status-' + container.ID));
                tr.append($("<td>").attr('id', 'image-' + container.ID));
                tr.append($("<td>").attr('id', 'port-' + container.ID));
                tr.append($("<td>").html('<button class="transparent-btn" onclick="getInfo(\'' + container.ID + '\')"><i class="bi bi-info-circle text-primary"></i></button>'));
                // first load, all rows are new so append in order the data was sent
                // TODO: previous loads, this appends newly created containers to the bottom of the table, which we don't want, but we need to be able to track state
                // if its the first load, append everything
                // if its a newly created container, will have to prepend
                if (firstLoad) {
                    tbody.append(tr);
                } else {
                    tbody.prepend(tr);
                }
            }

            // Define the attributes to be updated
            const attributes = ['Names', 'ID', 'State', 'Status', 'Image', 'Ports'];
            attributes.forEach(attr => {
                // If the attribute has changed
                if (previousState[container.ID]?.[attr] !== container[attr]) {
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
            previousState[container.ID] = container;
        });
        if (firstLoad) {
            firstLoad = false;
        }

        $("#loading").hide();
    };


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
        $.ajax({
            url: 'http://localhost:5002/api/system/prune',
            type: 'POST',
            success: function (result) {
            },
            error: function (result) {
                console.error(result);
            }
        })
    })

    // handle select all checkbox change
    $('#select-all').change(function () {
        // select all checkboxes with class of tr-checkbox and make them selected
        $('.tr-checkbox').prop('checked', this.checked);
        // enable/disable buttons
        if (this.checked) {
            $('#btn-stop, #btn-kill, #btn-restart, #btn-pause, #btn-delete, #btn-resume, #btn-start').removeClass('disabled');
        } else {
            // If no checkboxes are checked, disable all buttons
            $('#btn-stop, #btn-kill, #btn-restart, #btn-pause, #btn-delete, #btn-resume, #btn-start').addClass('disabled');
        }
    });
});

// Enables buttons after checkbox input
$(document).on('change', '.tr-checkbox', function () {
    const checkedCount = $('.tr-checkbox:checked').length;
    const buttonSelector = '#btn-stop, #btn-kill, #btn-restart, #btn-pause, #btn-delete, #btn-resume, #btn-start';

    $(buttonSelector).toggleClass('disabled', checkedCount === 0);
});