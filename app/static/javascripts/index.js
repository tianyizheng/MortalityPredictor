requirejs.config({
    baseUrl: '/static/javascripts',
    paths: {
        main: 'main',
        jquery: 'lib/jquery-3.3.1.min',
        bootstrap: 'lib/bootstrap.min',
        //jqueryui: 'lib/jquery-ui.min',
        d3: 'lib/d3.min',
        //socketio: '../socket.io/socket.io',
    }
});

if (!String.prototype.format) {
    String.prototype.format = function() {
        var args = arguments;
        return this.replace(/{(\d+)}/g, function(match, number) { 
            return typeof args[number] != 'undefined'
            ? args[number]
            : match
            ;
        });
    };
}

require(['main']);