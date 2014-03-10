$( document ).ready(function() {
			// Hide all objects initially
			$( "#init-players" ).hide();
			$( "#player-action" ).hide();
			// Hide voted action buttons until an action is voted
			var voted_action_list = $(".voted-action-btn");
			for (var i=0; i < voted_action_list.length; i++) {
				$(voted_action_list[i]).hide();
			}
			{% if show.running %}
				// Hide Nav Bar
				$( "#top-nav-bar" ).hide();
				run_show();
				function run_show(){
					var vote_end_played = false;
					var current_player = "";
					var hide_players_key = "{% for player_action in show.player_actions %}#player-{{forloop.counter}}{% if not forloop.last %},{% endif %}{% endfor %}";
					var start_time = new Date('{{show.start_time|date:"F j, Y H:i:s-0700"}}');
					var intervals = {{% for player_action in show.player_actions %}
										{{player_action.interval}}: "{{forloop.counter}}"{% if not forloop.last %},{% endif %}
									 {% endfor %}};
					// Hide all player divs
					$(hide_players_key).hide();
					// Run the interval change immediately
					change_interval();
					window.setInterval(function(){
					  change_interval();
					}, 3000);
					function change_interval(){
						var current_time = new Date();
						var elapsed_millis = current_time - start_time;
						var elapsed_total_seconds = parseInt(elapsed_millis / 1000);
						var elapsed_minutes = parseInt(elapsed_total_seconds / 60);
						console.log(elapsed_minutes);
						// If we've hit an interval
						if (elapsed_minutes in intervals) {
							var hide_vote_buttons = "#po-" + elapsed_minutes + "-1-btn,#po-"  + elapsed_minutes + "-2-btn,#po-" + elapsed_minutes + "-3-btn";
							// If the current player number is different than the interval player number
							if (current_player !== intervals[elapsed_minutes]) {
								// Set the current player number to the interval number
								current_player = intervals[elapsed_minutes];
								$("#player-" + current_player).show();
								$.playSound('{{host_url}}{{audio_path}}vote-chime');
								// Set the vote end sound to false
								vote_end_played = false;
							}
							// Get the vote action selector
							var voted_action_select = "#va-" + elapsed_minutes + "-btn";
							// Get the exact minute start of the interval
							var interval_start = new Date(start_time.getTime());
							interval_start.setMinutes(start_time.getMinutes() + elapsed_minutes);
							// Get the ending vote time of the interval
							var vote_end = new Date(interval_start.getTime());
							vote_end.setSeconds(interval_start.getSeconds() + {{VOTE_AFTER_INTERVAL}});
							var interval_url = "/actions_json/{{show.key.id}}/" + elapsed_minutes + "/";
							console.log(start_time.getTime());
							var crap = new Date();
							console.log(crap.getTime());
							console.log(interval_start.getTime());
							console.log(vote_end.getTime());
							console.log(interval_url);
							// If we're still in the {{VOTE_AFTER_INTERVAL}} second voting window
							if (current_time <= vote_end) {
								// Hide the final voted action button
								$("va-" + elapsed_minutes + "-btn").hide();
								// Set up the clock
								$('.glowingLayout').countdown({until: vote_end, compact: true, 
    								layout: '<span class="image{s10}"></span><span class="image{s1}"></span>'});
								$(".glowingLayout").show();
								// Pull from the json to get the voting options
								$.get(interval_url, function( data ) {
									console.log("Action fetch!");
									console.log(data);
									// If the user has already voted
									if ("voted" in data) {
										console.log("Voted!");
										// Hide the voting buttons
										$(hide_vote_buttons).hide();
										$(voted_action_select).show();
									}
									// Otherwise, set the voting options
									else {
										for (var option_num=0; option_num<=2; option_num++) {
											if (option_num < data.length) {
												var action_name = data[option_num]['name'];
												var action_id = data[option_num]['id'];
												var player_action_prefix = "#po-" + elapsed_minutes + "-" + (option_num + 1);
												$(player_action_prefix + "-act").attr('value', action_id);
												$(player_action_prefix + "-btn").attr('value', (option_num + 1) + ". " + action_name);
											}
										}
										// Show the voting buttons
										$(hide_vote_buttons).show();
									}
								});
							}
							// The {{VOTE_AFTER_INTERVAL}} second window has passed
							else {
								if ( vote_end_played === false) {
									$.playSound('{{host_url}}{{audio_path}}action-chime');
									vote_end_played = true;
								}
								$(".glowingLayout").hide();
								$(hide_vote_buttons).hide();
								$.get(interval_url, function( data ) {
									$(voted_action_select).html(data['current_action']);
									$(voted_action_select).show();
								});
							}
							$( "#player-action" ).show();
							// Hide all player divs
							$(hide_players_key).hide();
							// Show the current player
							$("#player-" + intervals[elapsed_minutes]).show();
						}
					}
				}
			{% endif %}
		});