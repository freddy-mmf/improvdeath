<script>
	$( document ).ready(function() {
		// Hide all objects initially
		$( "#init-players" ).hide();
		$( "#player-death" ).hide();
		$( "#default-screen" ).show();
		{% if show.running %}
			// Hide Nav Bar
			$( "#top-nav-bar" ).hide();
			var prev_event = "default-screen"
			doPoll();
		{% endif %}
		// Poll function that checks for a change every 5 seconds using "always"
		// "done" specifies what to do on a successful fetch
		function doPoll(){
			$.get('/show/{{show.key.id}}/show.json')
					.fail(
						function(data) {}
					)
					.done(
						function(data) {
							// Something has changed
							if (data.event !== prev_event) {
								// IF a player has died
								if (data.event === "player-death") {
									// Change the img source to the player that died
									var src = "{{player_image_path}}" + data.player_photo
									$("#player-death-img").attr("src", src);
									$("#player-death-cause").text(data.cause)
								}
								// Hide all divs
								$( "#init-players,#player-death,#default-screen" ).hide();
								// Show just the active event div
								$("#" + data.event).show();
								if (data.event !== "default-screen") {
									// Play bell toll
									$.playSound('{{host_url}}{{audio_path}}bell_toll');
								}
							}
							// Store the previous event
							prev_event = data.event
						}
					)
					.always(
						function() {
						setTimeout(doPoll, 5000);
						}
					);
		}
	});
</script>