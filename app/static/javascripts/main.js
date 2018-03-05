'use strict';

define(function(require){

	var $ = require('jquery');
	var Chart = require('Chart');
	var io = require('socketio');

	class Page{
		constructor(){
			this.socket = io.connect();

			var element = $('#patientChart');
			var chart = new Chart(element[0]);

			var patientSubmitButton = $('#patientSubmitButton').on('click', this.submitPatientRequest.bind(this));
			
			this.patientNameInput = $("#patientNameInput").keyup(function(event) {
				if (event.which === 13) {
					patientSubmitButton.click();
				}
			});

			this.socket.on('patient data', this.onPatientData.bind(this));
		}

		submitPatientRequest(event){
			var patientName = this.patientNameInput.val();
			this.socket.emit('get patient', {'name': patientName});
		}

		onPatientData(message){
			console.log(message);
		}

	}

	$(document).ready(function() { 
		var page = new Page();
	});

	return {};
});