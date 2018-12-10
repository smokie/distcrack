(function ($) {
    $.fn.simpletable = function (options) {
        var that = this;
        this.table = that;
        this.get = function () {

            $.getJSON(options.endpoint, {}, function (json) {
                if (!json.ok) {
                    return;
                }
                $.each(json.data, function (i, row) {
                        var tr = $('<tr/>');
                        $.each(row, function (k, v) {
                            if (k=="_id")
                                return true;
                            if (i == 0)
                                $(that.table).find('thead').append($('<th/>').html(k));
                            tr.append($('<td/>').html(v));
                            $(that.table).find('tbody').append(tr);
                        });
                        if (options.delete && typeof options.deleteUrl === 'string')
                        tr.append($('<td/>').append($('<a onclick="return confirm(\'Sure?\')" href="'+options.deleteUrl+'/'+row._id+'">Delete</a>')))
                });
            });
        }

        this.get();
    }
})(jQuery);
