
$(document).ready(function () {
    $('input[type="radio"]').prop('checked', false);
});

$(document).on('click', 'input[type="radio"]', function () {
    var status = $(this).closest('tr').find('td:eq(3)').text().trim();

    // First, disable all buttons
    $('#btn-stop, #btn-kill, #btn-restart, #btn-pause, #btn-resume, #btn-delete').addClass('disabled');

    // Then, enable the correct buttons based on the status
    if (status == "running") {
        $('#btn-stop, #btn-kill, #btn-restart, #btn-pause, #btn-delete').removeClass('disabled');
    } else if (status == "paused") {
        $('#btn-stop, #btn-kill, #btn-restart, #btn-resume, #btn-delete').removeClass('disabled');
    }
});