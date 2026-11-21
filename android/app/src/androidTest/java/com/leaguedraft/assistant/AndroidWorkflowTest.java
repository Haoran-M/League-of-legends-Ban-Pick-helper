package com.leaguedraft.assistant;

import static org.junit.Assert.*;

import android.content.pm.PackageInfo;
import android.content.pm.PackageManager;
import android.os.SystemClock;
import android.graphics.Point;
import android.view.MotionEvent;
import android.view.InputDevice;
import android.view.View;
import android.view.ViewGroup;

import androidx.test.core.app.ActivityScenario;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import androidx.test.platform.app.InstrumentationRegistry;
import androidx.test.uiautomator.By;
import androidx.test.uiautomator.UiDevice;
import androidx.test.uiautomator.UiObject2;
import androidx.test.uiautomator.Until;

import org.json.JSONObject;
import org.junit.Test;
import org.junit.runner.RunWith;

import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.atomic.AtomicReference;

@RunWith(AndroidJUnit4.class)
public class AndroidWorkflowTest {
    private MainActivity activity;

    private void waitReady() {
        long deadline = SystemClock.elapsedRealtime() + 45000;
        while (!activity.isReadyForTest()) {
            assertTrue("Android engine startup exceeded 45 seconds", SystemClock.elapsedRealtime() < deadline);
            SystemClock.sleep(50);
        }
    }

    private JSONObject view() throws Exception {
        AtomicReference<String> result = new AtomicReference<>();
        InstrumentationRegistry.getInstrumentation().runOnMainSync(() -> result.set(activity.stateForTest()));
        return new JSONObject(result.get());
    }

    private double command(String name, String args) throws Exception {
        int before = activity.analysisUpdates;
        long start = SystemClock.elapsedRealtime();
        InstrumentationRegistry.getInstrumentation().runOnMainSync(() -> {
            try { activity.commandForTest(name, args); } catch (Exception e) { throw new RuntimeException(e); }
        });
        while (activity.analysisUpdates == before) {
            assertTrue("Recommendation update exceeded 10 seconds for " + name, SystemClock.elapsedRealtime() - start < 10000);
            SystemClock.sleep(20);
        }
        return SystemClock.elapsedRealtime() - start;
    }

    private void pick(String team, int index, String name) throws Exception {
        command("assign", "{\"team\":\"" + team + "\",\"kind\":\"pick\",\"index\":" + index + ",\"champion\":\"" + name + "\"}");
    }

    private View findDescription(View node, String prefix) {
        if (node.getContentDescription() != null && node.getContentDescription().toString().startsWith(prefix)) return node;
        if (node instanceof ViewGroup) {
            ViewGroup group = (ViewGroup) node;
            for (int i = 0; i < group.getChildCount(); i++) { View found = findDescription(group.getChildAt(i), prefix); if (found != null) return found; }
        }
        return null;
    }

    private void drag(String source, String destination) {
        int before = activity.analysisUpdates;
        UiDevice device = UiDevice.getInstance(InstrumentationRegistry.getInstrumentation());
        UiObject2 from = device.wait(Until.findObject(By.descStartsWith(source)), 5000);
        UiObject2 to = device.wait(Until.findObject(By.descStartsWith(destination)), 5000);
        assertNotNull(source, from); assertNotNull(destination, to);
        from.drag(to.getVisibleCenter(), 600);
        InstrumentationRegistry.getInstrumentation().waitForIdleSync();
        long deadline = SystemClock.elapsedRealtime() + 10000;
        while (activity.analysisUpdates == before) {
            assertTrue("Drag update exceeded 10 seconds", SystemClock.elapsedRealtime() < deadline);
            SystemClock.sleep(20);
        }
    }

    private void send(long down, int action, float x, float y) {
        MotionEvent event = MotionEvent.obtain(down, SystemClock.uptimeMillis(), action, x, y, 0);
        event.setSource(InputDevice.SOURCE_TOUCHSCREEN);
        // Android 15's targeted injector rejects the system-owned drag surface.
        assertTrue(InstrumentationRegistry.getInstrumentation().getUiAutomation().injectInputEvent(event, true));
        event.recycle();
    }

    @Test public void offlineWorkflowAndTenSecondPickBudget() throws Exception {
        try (ActivityScenario<MainActivity> scenario = ActivityScenario.launch(MainActivity.class)) {
            scenario.onActivity(a -> activity = a); waitReady();
            PackageInfo info = activity.getPackageManager().getPackageInfo(activity.getPackageName(), PackageManager.GET_PERMISSIONS);
            if (info.requestedPermissions != null) for (String permission : info.requestedPermissions) assertNotEquals("android.permission.INTERNET", permission);
            command("reset", "{}");
            pick("blue", 0, "Garen"); pick("blue", 2, "Ahri");
            drag("blue pick 1:", "blue pick 3:");
            JSONObject state = view().getJSONObject("state");
            assertEquals("Ahri", state.getJSONArray("blue_picks").getJSONObject(0).getString("champion"));
            assertEquals("Garen", state.getJSONArray("blue_picks").getJSONObject(2).getString("champion"));
            drag("blue pick 1 role", "blue pick 3 role");
            state = view().getJSONObject("state");
            assertEquals("Mid", state.getJSONArray("blue_picks").getJSONObject(0).getString("role"));
            assertEquals("Top", state.getJSONArray("blue_picks").getJSONObject(2).getString("role"));
            pick("red", 0, "Ahri");
            assertTrue(view().getJSONObject("state").getJSONArray("red_picks").getJSONObject(0).isNull("champion"));
            command("reset", "{}");
            String[] names = {"Garen", "Lee Sin", "Ahri", "Jinx", "Leona", "Darius", "Amumu", "Akali", "Ashe", "Lux"};
            List<Double> latency = new ArrayList<>();
            for (int i = 0; i < 10; i++) {
                double time = command("assign", "{\"team\":\"" + (i < 5 ? "blue" : "red") + "\",\"kind\":\"pick\",\"index\":" + i % 5 + ",\"champion\":\"" + names[i] + "\"}");
                latency.add(time);
                assertTrue(time < 10000);
            }
            assertEquals(10, latency.size());
            android.util.Log.i("LeagueDraftTest", "PICK_LATENCY_MS=" + latency);
            command("reset", "{}"); command("undo", "{}");
            assertEquals("Lux", view().getJSONObject("state").getJSONArray("red_picks").getJSONObject(4).getString("champion"));
        }
    }

    @Test public void savedDraftSurvivesActivityRestart() throws Exception {
        try (ActivityScenario<MainActivity> scenario = ActivityScenario.launch(MainActivity.class)) {
            scenario.onActivity(a -> activity = a); waitReady(); command("remember", "{\"enabled\":true}");
            command("reset", "{}"); pick("blue", 2, "Orianna");
        }
        try (ActivityScenario<MainActivity> scenario = ActivityScenario.launch(MainActivity.class)) {
            scenario.onActivity(a -> activity = a); waitReady();
            assertEquals("Orianna", view().getJSONObject("state").getJSONArray("blue_picks").getJSONObject(2).getString("champion"));
            assertTrue(view().getBoolean("remember"));
        }
    }
}
