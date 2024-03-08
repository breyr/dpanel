$(document).on('click', 'input[type="checkbox"]', function () {
    var status = $(this).closest('tr').find('td:eq(3)').text().trim();
    var checkedCount = $('input[type="checkbox"]:checked').length;

    // Then, enable the correct buttons based on the status
    if (checkedCount > 0) {
        $('#btn-stop, #btn-kill, #btn-restart, #btn-pause, #btn-delete, #btn-resume, #btn-start').removeClass('disabled');
    } else {
        // If no checkboxes are checked, disable all buttons
        $('#btn-stop, #btn-kill, #btn-restart, #btn-pause, #btn-delete, #btn-resume, #btn-start').addClass('disabled');
    }
});