from datetime import timedelta

from sqlalchemy import update

from app.models import Game
from app.notify import get_notifier
from app.reminders import send_results
from test_auth import code, gql
from test_friends import PENDING, RESPOND, SEND, make_user
from test_picks import SAVE, mkgame, now  # noqa: F401  (now is a fixture)
from test_reminders import REGISTER, FakeNotifier
from test_sync import FakeClient, pl


async def player(client, handle, device=True):
    h, _ = await make_user(client, handle)
    if device:
        await gql(client, REGISTER, {"token": f"tok-{handle}", "platform": "ios"}, h)
    return h


async def befriend(client, a, b_handle, b):
    await gql(client, SEND, {"h": b_handle}, a)
    _, r = await gql(client, PENDING, headers=b)
    await gql(client, RESPOND, {"i": r["data"]["pendingRequests"][0]["id"], "a": True}, b)


async def pick(client, h, game, home, away):
    _, r = await gql(client, SAVE, {"g": str(game.id), "h": home, "a": away}, h)
    assert r["data"]["savePick"], r


async def final(session, game, home, away):
    await session.execute(
        update(Game).where(Game.id == game.id).values(status="final", home_score=home, away_score=away)
    )
    await session.commit()


async def run(session, clock):
    notifier = FakeNotifier()
    n = await send_results(session, notifier, clock)
    await session.commit()
    return n, {tokens[0]: (title, body) for tokens, title, body in notifier.sent}


async def test_a_final_game_pushes_each_friend_their_result_once(client, session, clock, now):
    josh, maria = await player(client, "josh"), await player(client, "maria")
    await befriend(client, josh, "maria", maria)
    g = await mkgame(session, now + timedelta(hours=1))
    await pick(client, josh, g, 24, 17)
    await pick(client, maria, g, 20, 17)
    assert (await run(session, clock))[0] == 0  # not final yet
    await final(session, g, 24, 17)
    n, sent = await run(session, clock)
    assert n == 2
    assert sent["tok-josh"] == ("Final: AWY 17, HOM 24", "You 3, @maria 1")
    assert sent["tok-maria"] == ("Final: AWY 17, HOM 24", "You 1, @josh 3")
    assert (await run(session, clock))[0] == 0  # the cron runs every 5 minutes; once is enough


async def test_only_players_who_picked_and_have_a_friend_hear_about_it(client, session, clock, now):
    josh, maria = await player(client, "josh"), await player(client, "maria")
    sam = await player(client, "sam")  # picked, but has no friends
    nodev = await player(client, "nodev", device=False)
    await befriend(client, josh, "maria", maria)
    await befriend(client, josh, "nodev", nodev)
    g = await mkgame(session, now + timedelta(hours=1))
    await pick(client, josh, g, 24, 17)
    await pick(client, sam, g, 24, 17)
    await pick(client, nodev, g, 10, 30)
    await final(session, g, 24, 17)
    n, sent = await run(session, clock)
    # maria made no pick: she scores nothing and is not told
    assert n == 1 and sent == {"tok-josh": ("Final: AWY 17, HOM 24", "You 2, @maria 0 · You 2, @nodev 0")}


async def test_games_that_finish_together_make_one_push(client, session, clock, now):
    josh, maria = await player(client, "josh"), await player(client, "maria")
    await befriend(client, josh, "maria", maria)
    g1 = await mkgame(session, now + timedelta(hours=1))
    g2 = await mkgame(session, now + timedelta(hours=1), ext="2")
    await pick(client, josh, g1, 24, 17)
    await pick(client, maria, g1, 20, 17)
    await pick(client, josh, g2, 10, 30)
    await final(session, g1, 24, 17)
    await final(session, g2, 21, 14)  # josh picked the loser, maria did not pick
    n, sent = await run(session, clock)
    assert n == 2
    assert sent["tok-josh"] == ("2 games final", "You 3, @maria 1")
    assert sent["tok-maria"] == ("Final: AWY 17, HOM 24", "You 1, @josh 3")  # she picked only one of them


async def test_a_long_friend_list_is_cut_short(client, session, clock, now):
    josh = await player(client, "josh")
    g = await mkgame(session, now + timedelta(hours=1))
    await pick(client, josh, g, 24, 17)
    for name in ("abe", "bea", "cal", "dee"):
        await befriend(client, josh, name, await player(client, name, device=False))
    await final(session, g, 24, 17)
    _, sent = await run(session, clock)
    assert sent["tok-josh"][1] == "You 2, @abe 0 · You 2, @bea 0 · You 2, @cal 0 +1 more"


async def test_the_sync_cron_sends_results_and_survives_a_push_failure(client, session, clock, now):
    from app.sync.espn import get_scoreboard_client

    josh, maria = await player(client, "josh"), await player(client, "maria")
    await befriend(client, josh, "maria", maria)
    g = await mkgame(session, now + timedelta(hours=1))
    await pick(client, josh, g, 24, 17)
    await final(session, g, 24, 17)
    notifier = FakeNotifier()
    app = client._transport.app
    app.dependency_overrides[get_scoreboard_client] = lambda: FakeClient(pl(1, type=4))
    app.dependency_overrides[get_notifier] = lambda: notifier
    secret = {"X-Sync-Secret": "test-sync-secret-0123456789"}
    r = await client.post("/internal/sync", headers=secret)
    assert r.status_code == 200 and [s[1] for s in notifier.sent] == ["Final: AWY 17, HOM 24"]

    class Broken:
        async def send(self, *a):
            raise RuntimeError("push service down")

    g2 = await mkgame(session, now + timedelta(hours=1), ext="2")
    await pick(client, josh, g2, 24, 17)
    await final(session, g2, 24, 17)
    app.dependency_overrides[get_notifier] = lambda: Broken()
    r = await client.post("/internal/sync", headers=secret)
    assert r.status_code == 200 and r.json() == {"nfl": 0, "cfb": 0}  # scores still sync


# the exact strings web/src/lib/account.ts sends
RESULT_PUSHES = "{ resultPushes }"
SET_RESULT_PUSHES = "mutation($on: Boolean!) { setResultPushes(on: $on) }"


async def test_a_player_can_mute_result_pushes_and_turn_them_back_on(client, session, clock, now):
    josh, maria = await player(client, "josh"), await player(client, "maria")
    await befriend(client, josh, "maria", maria)
    assert (await gql(client, RESULT_PUSHES, headers=josh))[1]["data"]["resultPushes"] is True  # on until muted
    _, r = await gql(client, SET_RESULT_PUSHES, {"on": False}, josh)
    assert r["data"]["setResultPushes"] is False
    assert (await gql(client, RESULT_PUSHES, headers=josh))[1]["data"]["resultPushes"] is False
    assert (await gql(client, RESULT_PUSHES, headers=maria))[1]["data"]["resultPushes"] is True

    g = await mkgame(session, now + timedelta(hours=1))
    await pick(client, josh, g, 24, 17)
    await pick(client, maria, g, 20, 17)
    await final(session, g, 24, 17)
    n, sent = await run(session, clock)
    assert n == 1 and list(sent) == ["tok-maria"]  # his friend still hears how she did against him

    await gql(client, SET_RESULT_PUSHES, {"on": True}, josh)
    g2 = await mkgame(session, now + timedelta(hours=1), ext="2")
    await pick(client, josh, g2, 24, 17)
    await final(session, g2, 24, 17)
    _, sent = await run(session, clock)
    assert list(sent) == ["tok-josh"]


async def test_the_result_push_setting_needs_login(client):
    assert code((await gql(client, RESULT_PUSHES))[1]) == "UNAUTHENTICATED"
    assert code((await gql(client, SET_RESULT_PUSHES, {"on": False}))[1]) == "UNAUTHENTICATED"
