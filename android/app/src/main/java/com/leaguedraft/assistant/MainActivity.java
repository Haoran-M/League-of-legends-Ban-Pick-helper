package com.leaguedraft.assistant;

import android.app.Activity;
import android.app.AlertDialog;
import android.app.Dialog;
import android.content.ClipData;
import android.content.Intent;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.graphics.Color;
import android.graphics.ColorMatrix;
import android.graphics.ColorMatrixColorFilter;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.os.SystemClock;
import android.text.Editable;
import android.text.InputType;
import android.text.TextWatcher;
import android.util.LruCache;
import android.view.DragEvent;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.view.WindowInsets;
import android.view.inputmethod.InputMethodManager;
import android.widget.AdapterView;
import android.widget.ArrayAdapter;
import android.widget.BaseAdapter;
import android.widget.Button;
import android.widget.CheckBox;
import android.widget.EditText;
import android.widget.FrameLayout;
import android.widget.GridView;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.Spinner;
import android.widget.TextView;
import android.widget.Toast;

import com.chaquo.python.PyObject;
import com.chaquo.python.Python;
import com.chaquo.python.android.AndroidPlatform;

import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;

import java.io.File;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.io.OutputStream;
import java.nio.charset.StandardCharsets;
import java.text.Normalizer;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/** Fully local Android UI. All Python and database work stays on one worker. */
public class MainActivity extends Activity {
    private static final int BACKGROUND = Color.rgb(16, 21, 30);
    private static final int PANEL = Color.rgb(22, 30, 43);
    private static final int TEXT = Color.rgb(229, 236, 247);
    private static final int MUTED = Color.rgb(159, 177, 201);
    private static final int CYAN = Color.rgb(108, 214, 237);
    private static final int IMPORT_DATA = 40, EXPORT_DRAFT = 41;
    private static final ExecutorService APP_WORKER = Executors.newSingleThreadExecutor();
    private final ExecutorService worker = APP_WORKER;
    private final Handler main = new Handler(Looper.getMainLooper());
    private final LruCache<String, Bitmap> portraits = new LruCache<>(180);
    private final List<String> championNames = new ArrayList<>();
    private final Map<String, String> aliases = new HashMap<>();
    private final Map<String, Slot> slots = new HashMap<>();
    private final Map<String, TextView> roleButtons = new HashMap<>();
    private final Set<String> picked = new HashSet<>(), banned = new HashSet<>();
    private final String[] roles = {"Top", "Jungle", "Mid", "ADC", "Support"};
    private JSONObject viewState;
    private PyObject bridge;
    private LinearLayout draftContent, analysisContent, resultsContainer;
    private FrameLayout pageHost;
    private View draftPage, analysisPage;
    private TextView status, draftSummary, analysisStatus, sourceInfo, activeLabel, responseTime;
    private Spinner userTeam, userRole, dataset, rank, region;
    private CheckBox remember;
    private Button undo;
    private boolean rendering;
    private volatile boolean ready, destroyed;
    private int generation, activeIndex;
    private String activeTeam = "blue", activeKind = "pick";
    private long lastPickAt;
    private Runnable pendingAnalysis;
    public volatile double lastResponseMs = -1;
    public volatile int analysisUpdates;

    @Override public void onCreate(Bundle saved) {
        super.onCreate(saved);
        getWindow().setStatusBarColor(BACKGROUND);
        getWindow().setNavigationBarColor(BACKGROUND);
        LinearLayout root = vertical();
        root.setBackgroundColor(BACKGROUND);
        root.setPadding(dp(12), dp(8), dp(12), dp(8));
        root.setOnApplyWindowInsetsListener((v, insets) -> {
            v.setPadding(dp(12) + insets.getSystemWindowInsetLeft(), dp(8) + insets.getSystemWindowInsetTop(),
                    dp(12) + insets.getSystemWindowInsetRight(), dp(8) + insets.getSystemWindowInsetBottom());
            return insets;
        });
        setContentView(root);
        TextView title = text("LEAGUE / DRAFT", 23, TEXT);
        title.setTypeface(null, Typeface.BOLD);
        root.addView(title);
        root.addView(text("Offline draft workspace · Manual input", 12, MUTED));
        LinearLayout identity = horizontal();
        userTeam = spinner(new String[]{"Blue", "Red"}, "Your team");
        userRole = spinner(roles, "Your role");
        identity.addView(userTeam, weight()); identity.addView(userRole, weight());
        Button settings = button("Settings", () -> showSettings());
        identity.addView(settings, weight()); root.addView(identity);
        userTeam.setOnItemSelectedListener(selection(() -> {
            if (viewState != null) {
                String value = userTeam.getSelectedItemPosition() == 0 ? "blue" : "red";
                if (!value.equals(state().optString("user_team"))) action("set_user", json("team", value));
            }
        }));
        userRole.setOnItemSelectedListener(selection(() -> {
            String value = userRole.getSelectedItem().toString();
            if (viewState != null && !value.equals(state().optString("user_role"))) action("set_user", json("role", value));
        }));
        LinearLayout tools = horizontal();
        remember = new CheckBox(this); remember.setText("Save draft"); remember.setTextColor(TEXT); remember.setTextSize(12);
        remember.setContentDescription("Save draft between app launches");
        remember.setOnCheckedChangeListener((b, checked) -> { if (ready && !rendering) action("remember", json("enabled", checked)); });
        tools.addView(remember, weight());
        undo = button("Undo", () -> action("undo", new JSONObject())); tools.addView(undo, weight());
        tools.addView(button("Reset", () -> action("reset", new JSONObject())), weight()); root.addView(tools);
        LinearLayout tabs = horizontal();
        tabs.addView(button("Draft", () -> showPage(false)), weight());
        tabs.addView(button("Analysis", () -> showPage(true)), weight());
        root.addView(tabs);
        pageHost = new FrameLayout(this); root.addView(pageHost, new LinearLayout.LayoutParams(-1, 0, 1));
        draftContent = vertical();
        draftPage = scroll(draftContent); pageHost.addView(draftPage);
        draftContent.addView(teamCard("blue")); draftContent.addView(teamCard("red"));
        activeLabel = text("Blue pick 1", 15, CYAN); draftContent.addView(activeLabel);
        LinearLayout choose = horizontal();
        choose.addView(button("Choose champion", this::showChampions), new LinearLayout.LayoutParams(0, dp(48), 2));
        choose.addView(button("Clear slot", () -> action("assign", targetPayload(activeTeam, activeKind, activeIndex, null))), weight());
        draftContent.addView(choose);
        draftContent.addView(text("Tap a slot to choose. Hold and drag portraits or role labels to swap.", 12, MUTED));
        draftSummary = text("Preparing local data…", 14, TEXT); draftSummary.setPadding(0, dp(12), 0, dp(12));
        draftContent.addView(draftSummary);
        analysisContent = vertical(); analysisPage = scroll(analysisContent); pageHost.addView(analysisPage); analysisPage.setVisibility(View.GONE);
        analysisContent.addView(text("HISTORICAL COMPARISONS", 18, CYAN));
        dataset = spinner(new String[]{"Loading patches…"}, "Historical patch and dataset"); analysisContent.addView(dataset);
        LinearLayout filters = horizontal();
        rank = spinner(new String[]{"PRO"}, "Rank or competition level"); region = spinner(new String[]{"GLOBAL"}, "Region or professional league");
        filters.addView(rank, weight()); filters.addView(region, weight()); analysisContent.addView(filters);
        dataset.setOnItemSelectedListener(selection(this::filtersChanged));
        rank.setOnItemSelectedListener(selection(this::filtersChanged));
        region.setOnItemSelectedListener(selection(this::filtersChanged));
        sourceInfo = text("", 12, MUTED); sourceInfo.setTextIsSelectable(true); analysisContent.addView(sourceInfo);
        responseTime = text("", 12, CYAN); responseTime.setContentDescription("Recommendation update time"); analysisContent.addView(responseTime);
        analysisStatus = text("Preparing historical data…", 14, TEXT); analysisContent.addView(analysisStatus);
        LinearLayout dataButtons = horizontal();
        dataButtons.addView(button("Import JSON", this::chooseImport), weight());
        dataButtons.addView(button("Export draft", this::exportDraft), weight());
        dataButtons.addView(button("Sources", this::showSources), weight()); analysisContent.addView(dataButtons);
        resultsContainer = vertical(); analysisContent.addView(resultsContainer);
        status = text("Starting the local engine…", 12, MUTED); status.setPadding(0, dp(5), 0, 0); root.addView(status);
        worker.execute(this::initialize);
    }

    private void initialize() {
        try {
            File seed = new File(getNoBackupFilesDir(), "seed.sqlite3");
            if (!seed.isFile() || getPreferences(MODE_PRIVATE).getInt("seedVersion", -1) != BuildConfig.VERSION_CODE) {
                copyAsset("seed.sqlite3", seed);
                getPreferences(MODE_PRIVATE).edit().putInt("seedVersion", BuildConfig.VERSION_CODE).apply();
            }
            JSONObject roster = new JSONObject(assetText("champions.json"));
            JSONArray names = roster.getJSONArray("names");
            List<String> loadedNames = new ArrayList<>();
            for (int i = 0; i < names.length(); i++) loadedNames.add(names.getString(i));
            Map<String, String> loadedAliases = new HashMap<>();
            JSONObject rawAliases = roster.getJSONObject("aliases");
            java.util.Iterator<String> keys = rawAliases.keys();
            while (keys.hasNext()) { String key = keys.next(); loadedAliases.put(normalize(key), rawAliases.getString(key)); }
            if (!Python.isStarted()) Python.start(new AndroidPlatform(getApplicationContext()));
            bridge = Python.getInstance().getModule("mobile_bridge");
            JSONObject response = new JSONObject(bridge.callAttr("initialize", getFilesDir().getAbsolutePath(), seed.getAbsolutePath()).toString());
            main.post(() -> {
                if (destroyed) return;
                championNames.addAll(loadedNames); aliases.putAll(loadedAliases); ready = true;
                render(response); status.setText(response.optString("notice").isEmpty() ? "Ready · Offline · Long-press portraits or roles to swap" : response.optString("notice"));
                scheduleAnalysis(generation, SystemClock.elapsedRealtime());
            });
        } catch (Exception e) { fail("Could not prepare local data", e); }
    }

    private View teamCard(String team) {
        LinearLayout card = vertical(); card.setPadding(dp(8), dp(8), dp(8), dp(8));
        card.setBackground(background(PANEL, Color.rgb(42, 55, 75), 1));
        LinearLayout.LayoutParams cardParams = new LinearLayout.LayoutParams(-1, -2); cardParams.setMargins(0, dp(6), 0, dp(6)); card.setLayoutParams(cardParams);
        card.addView(text(team.toUpperCase(Locale.ROOT) + " SIDE", 15, team.equals("blue") ? Color.rgb(140, 200, 255) : Color.rgb(255, 171, 184)));
        LinearLayout pickRow = horizontal(), roleRow = horizontal(), banRow = horizontal();
        for (int i = 0; i < 5; i++) {
            final int index = i;
            Slot pick = new Slot(team, "pick", index); slots.put(pick.key(), pick);
            pickRow.addView(pick.cell, weight());
            TextView role = text("Unknown", 11, MUTED); role.setGravity(Gravity.CENTER); role.setMinHeight(dp(48));
            role.setBackground(background(Color.rgb(17, 26, 39), Color.rgb(52, 68, 91), 1));
            role.setContentDescription(team + " pick " + (i + 1) + " role");
            role.setOnClickListener(v -> chooseRole(team, index));
            role.setOnLongClickListener(v -> {
                v.startDragAndDrop(ClipData.newPlainText("role", team + ":" + index), new View.DragShadowBuilder(v), new RoleDrag(team, index), 0); return true;
            });
            role.setOnDragListener((v, event) -> roleDrag(team, index, v, event));
            roleButtons.put(team + index, role); roleRow.addView(role, weight());
            Slot ban = new Slot(team, "ban", index); slots.put(ban.key(), ban); banRow.addView(ban.cell, weight());
        }
        card.addView(pickRow); card.addView(roleRow); card.addView(text("BANS", 10, MUTED)); card.addView(banRow);
        return card;
    }

    private final class Slot {
        final String team, kind; final int index;
        String champion;
        final LinearLayout cell; final ImageView image; final TextView name;
        Slot(String team, String kind, int index) {
            this.team = team; this.kind = kind; this.index = index;
            cell = vertical(); cell.setGravity(Gravity.CENTER); cell.setPadding(dp(2), dp(3), dp(2), dp(3));
            image = new ImageView(MainActivity.this); image.setScaleType(ImageView.ScaleType.CENTER_CROP);
            int size = dp(kind.equals("pick") ? 44 : 30);
            cell.addView(image, new LinearLayout.LayoutParams(size, size));
            name = text("" + (index + 1), 10, TEXT); name.setGravity(Gravity.CENTER); name.setMaxLines(2); cell.addView(name);
            cell.setContentDescription(team + " " + kind + " " + (index + 1));
            cell.setOnClickListener(v -> { select(this); showChampions(); });
            cell.setOnLongClickListener(v -> {
                if (champion == null) return false;
                boolean started = v.startDragAndDrop(ClipData.newPlainText("champion", champion), new View.DragShadowBuilder(image), this, 0);
                if (BuildConfig.DEBUG) android.util.Log.d("LeagueDraftDrag", "start " + key() + "=" + started);
                return started;
            });
            cell.setOnDragListener((v, event) -> {
                if (BuildConfig.DEBUG && (event.getAction() == DragEvent.ACTION_DRAG_STARTED || event.getAction() == DragEvent.ACTION_DROP)) android.util.Log.d("LeagueDraftDrag", key() + " action=" + event.getAction() + " local=" + (event.getLocalState() == null ? "null" : event.getLocalState().getClass().getSimpleName()));
                if (!(event.getLocalState() instanceof Slot)) return false;
                Slot source = (Slot) event.getLocalState();
                if (!source.kind.equals(kind)) return false;
                if (event.getAction() == DragEvent.ACTION_DRAG_ENTERED) cell.setAlpha(.5f);
                if (event.getAction() == DragEvent.ACTION_DRAG_EXITED || event.getAction() == DragEvent.ACTION_DRAG_ENDED) cell.setAlpha(1);
                if (event.getAction() == DragEvent.ACTION_DROP) {
                    cell.setAlpha(1); select(this);
                    action("swap", json("source", targetPayload(source.team, source.kind, source.index, source.champion),
                            "destination", targetPayload(team, kind, index, champion)));
                }
                return true;
            });
        }
        String key() { return team + ":" + kind + ":" + index; }
    }

    private static final class RoleDrag {
        final String team; final int index;
        RoleDrag(String team, int index) { this.team = team; this.index = index; }
    }

    private boolean roleDrag(String team, int index, View target, DragEvent event) {
        if (!(event.getLocalState() instanceof RoleDrag)) return false;
        RoleDrag source = (RoleDrag) event.getLocalState();
        if (!team.equals(source.team)) return false;
        if (event.getAction() == DragEvent.ACTION_DRAG_ENTERED) target.setAlpha(.5f);
        if (event.getAction() == DragEvent.ACTION_DRAG_EXITED || event.getAction() == DragEvent.ACTION_DRAG_ENDED) target.setAlpha(1);
        if (event.getAction() == DragEvent.ACTION_DROP) {
            target.setAlpha(1);
            action("swap_roles", json("source_team", source.team, "team", team, "source", source.index, "destination", index));
        }
        return true;
    }

    private void select(Slot slot) {
        activeTeam = slot.team; activeKind = slot.kind; activeIndex = slot.index; updateActive();
    }

    private void updateActive() {
        activeLabel.setText(capitalize(activeTeam) + " " + activeKind + " " + (activeIndex + 1));
        for (Slot slot : slots.values()) {
            boolean selected = slot.team.equals(activeTeam) && slot.kind.equals(activeKind) && slot.index == activeIndex;
            slot.cell.setBackground(background(selected ? Color.rgb(24, 60, 80) : Color.rgb(32, 44, 62), selected ? CYAN : Color.rgb(52, 68, 91), selected ? 2 : 1));
        }
    }

    private void showChampions() {
        if (!ready) return;
        Dialog dialog = new Dialog(this);
        dialog.setTitle(capitalize(activeTeam) + " " + activeKind + " " + (activeIndex + 1));
        LinearLayout content = vertical(); content.setBackgroundColor(BACKGROUND); content.setPadding(dp(12), dp(10), dp(12), dp(10));
        TextView heading = text("Choose for " + capitalize(activeTeam) + " " + activeKind + " " + (activeIndex + 1), 19, CYAN); content.addView(heading);
        EditText search = new EditText(this); search.setSingleLine(true); search.setTextColor(TEXT); search.setHintTextColor(MUTED);
        search.setHint("Search champion or alias"); search.setContentDescription("Search champions"); content.addView(search);
        content.addView(text("Grayscale = picked or banned. Tap an available champion.", 12, MUTED));
        GridView grid = new GridView(this); grid.setNumColumns(getResources().getConfiguration().screenWidthDp >= 600 ? 6 : 4);
        grid.setVerticalSpacing(dp(6)); grid.setHorizontalSpacing(dp(6)); grid.setStretchMode(GridView.STRETCH_COLUMN_WIDTH);
        ChampionAdapter adapter = new ChampionAdapter(); grid.setAdapter(adapter);
        content.addView(grid, new LinearLayout.LayoutParams(-1, 0, 1));
        search.addTextChangedListener(new TextWatcher() {
            @Override public void beforeTextChanged(CharSequence s, int a, int c, int after) { }
            @Override public void onTextChanged(CharSequence s, int start, int before, int count) { adapter.filter(s.toString()); }
            @Override public void afterTextChanged(Editable e) { }
        });
        grid.setOnItemClickListener((parent, v, position, id) -> {
            String name = adapter.visible.get(position);
            dialog.dismiss();
            ((InputMethodManager)getSystemService(INPUT_METHOD_SERVICE)).hideSoftInputFromWindow(search.getWindowToken(), 0);
            action("assign", targetPayload(activeTeam, activeKind, activeIndex, name));
        });
        content.addView(button("Cancel", dialog::dismiss));
        dialog.setContentView(content);
        dialog.show();
        if (dialog.getWindow() != null) dialog.getWindow().setLayout(-1, -1);
    }

    private final class ChampionAdapter extends BaseAdapter {
        final List<String> visible = new ArrayList<>(championNames);
        void filter(String query) {
            String normalized = normalize(query); visible.clear();
            for (String name : championNames) {
                boolean match = normalize(name).contains(normalized);
                if (!match) for (Map.Entry<String, String> alias : aliases.entrySet()) if (alias.getValue().equals(name) && alias.getKey().contains(normalized)) { match = true; break; }
                if (match) visible.add(name);
            }
            notifyDataSetChanged();
        }
        @Override public int getCount() { return visible.size(); }
        @Override public Object getItem(int position) { return visible.get(position); }
        @Override public long getItemId(int position) { return position; }
        @Override public View getView(int position, View recycled, ViewGroup parent) {
            LinearLayout tile;
            if (recycled instanceof LinearLayout) tile = (LinearLayout) recycled;
            else {
                tile = vertical(); tile.setGravity(Gravity.CENTER); tile.setPadding(dp(3), dp(4), dp(3), dp(4));
                ImageView image = new ImageView(MainActivity.this); image.setScaleType(ImageView.ScaleType.CENTER_CROP);
                tile.addView(image, new LinearLayout.LayoutParams(dp(58), dp(58)));
                TextView label = text("", 11, TEXT); label.setGravity(Gravity.CENTER); label.setMinHeight(dp(33)); label.setMaxLines(2); tile.addView(label);
            }
            String name = visible.get(position); boolean used = picked.contains(name) || banned.contains(name);
            ImageView image = (ImageView) tile.getChildAt(0); image.setImageBitmap(portrait(name));
            if (used) { ColorMatrix matrix = new ColorMatrix(); matrix.setSaturation(0); image.setColorFilter(new ColorMatrixColorFilter(matrix)); }
            else image.clearColorFilter();
            ((TextView)tile.getChildAt(1)).setText(name);
            tile.setAlpha(used ? .6f : 1); tile.setBackground(background(PANEL, Color.rgb(52, 68, 91), 1));
            tile.setContentDescription(name + (used ? ", picked or banned" : ", available"));
            return tile;
        }
    }

    private void chooseRole(String team, int index) {
        if (!ready) return;
        String[] choices = {"Unknown", "Top", "Jungle", "Mid", "ADC", "Support"};
        new AlertDialog.Builder(this).setTitle(capitalize(team) + " pick " + (index + 1) + " role")
                .setItems(choices, (dialog, which) -> action("set_role", json("team", team, "index", index, "role", which == 0 ? JSONObject.NULL : choices[which]))).show();
    }

    private void action(String command, JSONObject arguments) {
        if (!ready || destroyed) return;
        final int token = ++generation;
        lastPickAt = SystemClock.elapsedRealtime();
        if (pendingAnalysis != null) main.removeCallbacks(pendingAnalysis);
        status.setText("Updating local draft…");
        worker.execute(() -> {
            try {
                JSONObject response = new JSONObject(bridge.callAttr("dispatch", command, arguments.toString()).toString());
                main.post(() -> {
                    if (destroyed || token != generation) return;
                    render(response);
                    if (!response.optBoolean("ok")) {
                        String error = response.optString("error", "Edit rejected"); status.setText(error); Toast.makeText(this, error, Toast.LENGTH_LONG).show();
                    } else status.setText(response.optString("notice").isEmpty() ? "Draft updated · Offline" : response.optString("notice"));
                    scheduleAnalysis(token, lastPickAt);
                });
            } catch (Exception e) { fail("Could not update the draft", e); }
        });
    }

    private void scheduleAnalysis(int token, long pickAt) {
        if (pendingAnalysis != null) main.removeCallbacks(pendingAnalysis);
        analysisStatus.setText("Updating recommendations…");
        pendingAnalysis = () -> worker.execute(() -> {
            try {
                JSONObject report = new JSONObject(bridge.callAttr("analyze").toString());
                main.post(() -> {
                    if (destroyed || token != generation) return;
                    renderAnalysis(report);
                    analysisUpdates++;
                    if (pickAt > 0) {
                        lastResponseMs = SystemClock.elapsedRealtime() - pickAt;
                        responseTime.setText(String.format(Locale.US, "Updated in %.2f s · target under 10 s", lastResponseMs / 1000));
                    }
                });
            } catch (Exception e) { fail("Recommendations unavailable", e); }
        });
        main.postDelayed(pendingAnalysis, 120);
    }

    private void render(JSONObject response) {
        rendering = true;
        try {
            viewState = response; JSONObject state = response.getJSONObject("state");
            picked.clear(); banned.clear();
            int pickCount = 0, banCount = 0;
            for (Slot slot : slots.values()) {
                JSONArray entries = state.getJSONArray(slot.team + "_" + slot.kind + "s");
                String name;
                if (slot.kind.equals("pick")) {
                    JSONObject pick = entries.getJSONObject(slot.index);
                    name = pick.isNull("champion") ? null : pick.getString("champion");
                    roleButtons.get(slot.team + slot.index).setText(pick.isNull("role") ? "Unknown" : pick.getString("role"));
                    if (name != null) { picked.add(name); pickCount++; }
                } else {
                    name = entries.isNull(slot.index) ? null : entries.getString(slot.index);
                    if (name != null) { banned.add(name); banCount++; }
                }
                slot.champion = name; slot.image.setImageBitmap(name == null ? null : portrait(name));
                slot.name.setText(name == null ? "" + (slot.index + 1) : name);
                slot.cell.setContentDescription(slot.team + " " + slot.kind + " " + (slot.index + 1) + ": " + (name == null ? "empty" : name));
            }
            userTeam.setSelection(state.getString("user_team").equals("blue") ? 0 : 1);
            userRole.setSelection(java.util.Arrays.asList(roles).indexOf(state.getString("user_role")));
            remember.setChecked(response.optBoolean("remember")); undo.setEnabled(response.optBoolean("can_undo"));
            draftSummary.setText(pickCount + "/10 picks · " + banCount + "/10 bans\nOpen Analysis for evidence and comparisons.");
            JSONArray datasets = response.getJSONArray("datasets");
            List<String> datasetTitles = new ArrayList<>(); int selected = 0;
            JSONObject filters = response.optJSONObject("filters");
            for (int i = 0; i < datasets.length(); i++) {
                JSONObject row = datasets.getJSONObject(i);
                datasetTitles.add((row.optInt("is_demo") == 1 ? "DEMO · " : "Historical · ") + row.getString("patch"));
                if (filters != null && row.getString("id").equals(filters.optString("dataset_id"))) selected = i;
            }
            setOptions(dataset, datasetTitles, selected);
            setOptions(rank, strings(response.getJSONArray("ranks")), filters == null ? "" : filters.optString("rank"));
            setOptions(region, strings(response.getJSONArray("regions")), filters == null ? "" : filters.optString("region"));
            JSONObject metadata = response.optJSONObject("metadata");
            if (metadata != null) sourceInfo.setText((metadata.optInt("is_demo") == 1 ? "DEMO / SYNTHETIC — not historical\n" : "PROFESSIONAL HISTORICAL PLAY — not solo queue\n")
                    + metadata.optString("license") + " · " + metadata.optString("source") + "\n" + metadata.optString("notes"));
            updateActive();
            if (!response.optString("notice").isEmpty()) status.setText(response.optString("notice"));
        } catch (JSONException e) { fail("Local state could not be displayed", e); }
        finally { rendering = false; }
    }

    private void renderAnalysis(JSONObject report) {
        try {
            JSONArray results = report.getJSONArray("results"); int supported = 0;
            for (int i = 0; i < results.length(); i++) if (!results.getJSONObject(i).isNull("score")) supported++;
            analysisStatus.setText((supported == 0 ? "Insufficient statistical evidence." : supported + " supported / " + results.length() + " role-eligible candidates.")
                    + "\n" + String.join(" · ", strings(report.optJSONArray("gaps"))));
            resultsContainer.removeAllViews();
            StringBuilder summary = new StringBuilder();
            for (int i = 0; i < results.length(); i++) {
                JSONObject candidate = results.getJSONObject(i);
                boolean scored = !candidate.isNull("score");
                if (i < 3 && scored) {
                    if (summary.length() > 0) summary.append(" · ");
                    summary.append(candidate.getString("name")).append(' ').append(String.format(Locale.US, "%.1f", candidate.getDouble("score")));
                }
                if (i >= 20) continue;
                LinearLayout row = horizontal(); row.setGravity(Gravity.CENTER_VERTICAL); row.setPadding(dp(8), dp(7), dp(8), dp(7));
                row.setBackground(background(PANEL, Color.rgb(42, 55, 75), 1));
                LinearLayout.LayoutParams rowParams = new LinearLayout.LayoutParams(-1, -2); rowParams.setMargins(0, dp(3), 0, dp(3));
                ImageView image = new ImageView(this); image.setImageBitmap(portrait(candidate.getString("name"))); row.addView(image, new LinearLayout.LayoutParams(dp(40), dp(40)));
                LinearLayout labels = vertical(); labels.setPadding(dp(10), 0, dp(6), 0);
                labels.addView(text(candidate.getString("name"), 15, TEXT));
                JSONObject baseline = candidate.optJSONObject("baseline");
                labels.addView(text(String.format(Locale.US, "Coverage %.0f%% · base n %s", candidate.optDouble("coverage") * 100, baseline == null ? "—" : baseline.optInt("games")), 12, MUTED));
                row.addView(labels, new LinearLayout.LayoutParams(0, -2, 1));
                row.addView(text(scored ? String.format(Locale.US, "%.1f", candidate.getDouble("score")) : "—", 21, scored ? CYAN : MUTED));
                row.setContentDescription("Candidate " + candidate.getString("name"));
                row.setOnClickListener(v -> showText(candidate.optString("name"), candidate.optString("details")));
                resultsContainer.addView(row, rowParams);
            }
            if (summary.length() > 0) draftSummary.setText("Top comparisons: " + summary + "\nScores are not win probabilities. Tap Analysis for evidence.");
            else draftSummary.setText("Insufficient statistical evidence at these filters. Open Analysis to inspect support.");
            resultsContainer.addView(text("Scores are comparisons, not win probabilities. Pair samples overlap and must not be summed.", 12, MUTED));
        } catch (JSONException e) { fail("Evidence could not be displayed", e); }
    }

    private void filtersChanged() {
        if (!ready || rendering || viewState == null || dataset.getSelectedItemPosition() < 0) return;
        try {
            JSONObject selected = viewState.getJSONArray("datasets").getJSONObject(dataset.getSelectedItemPosition());
            JSONObject old = viewState.optJSONObject("filters");
            String id = selected.getString("id"), r = String.valueOf(rank.getSelectedItem()), area = String.valueOf(region.getSelectedItem());
            if (old != null && id.equals(old.optString("dataset_id")) && r.equals(old.optString("rank")) && area.equals(old.optString("region"))) return;
            action("set_filters", json("dataset_id", id, "rank", r, "region", area));
        } catch (JSONException e) { fail("Filter unavailable", e); }
    }

    private void showSettings() {
        if (!ready || viewState == null) return;
        try {
            JSONObject settings = viewState.getJSONObject("settings"), weights = settings.getJSONObject("weights");
            LinearLayout form = vertical(); form.setPadding(dp(18), dp(8), dp(18), dp(8));
            String[] keys = {"lane", "other_enemy", "synergy", "composition", "baseline", "robustness"};
            String[] titles = {"Lane matchup", "Other enemies", "Ally synergy", "Composition heuristic", "Baseline", "Blind robustness"};
            Map<String, EditText> fields = new HashMap<>();
            for (int i = 0; i < keys.length; i++) {
                form.addView(text(titles[i], 13, TEXT)); EditText field = number(weights.getDouble(keys[i])); fields.put(keys[i], field); form.addView(field);
            }
            form.addView(text("Smoothing prior strength", 13, TEXT)); EditText alpha = number(settings.getDouble("alpha")); form.addView(alpha);
            form.addView(text("Minimum observations", 13, TEXT)); EditText minimum = number(settings.getInt("minimum_games")); minimum.setInputType(InputType.TYPE_CLASS_NUMBER); minimum.setText(String.valueOf(settings.getInt("minimum_games"))); form.addView(minimum);
            new AlertDialog.Builder(this).setTitle("Scoring settings").setView(scroll(form)).setNegativeButton("Cancel", null)
                    .setPositiveButton("Save", (dialog, which) -> {
                        try {
                            JSONObject changedWeights = new JSONObject(); for (String key : keys) changedWeights.put(key, Double.parseDouble(fields.get(key).getText().toString()));
                            action("set_settings", json("weights", changedWeights, "alpha", Double.parseDouble(alpha.getText().toString()), "minimum_games", Integer.parseInt(minimum.getText().toString().trim())));
                        } catch (Exception e) { Toast.makeText(this, "Enter valid nonnegative weights and positive support settings.", Toast.LENGTH_LONG).show(); }
                    }).show();
        } catch (JSONException e) { fail("Settings unavailable", e); }
    }

    private void chooseImport() {
        if (!ready) return;
        Intent intent = new Intent(Intent.ACTION_OPEN_DOCUMENT); intent.addCategory(Intent.CATEGORY_OPENABLE);
        intent.setType("*/*"); intent.putExtra(Intent.EXTRA_MIME_TYPES, new String[]{"application/json", "text/plain"});
        startActivityForResult(intent, IMPORT_DATA);
    }

    private void exportDraft() {
        if (!ready) return;
        Intent intent = new Intent(Intent.ACTION_CREATE_DOCUMENT); intent.addCategory(Intent.CATEGORY_OPENABLE);
        intent.setType("application/json"); intent.putExtra(Intent.EXTRA_TITLE, "league-draft.json"); startActivityForResult(intent, EXPORT_DRAFT);
    }

    @Override protected void onActivityResult(int request, int result, Intent data) {
        super.onActivityResult(request, result, data);
        if (result != RESULT_OK || data == null || data.getData() == null) return;
        Uri uri = data.getData();
        worker.execute(() -> {
            try {
                if (request == IMPORT_DATA) {
                    File file = new File(getFilesDir(), "import.json");
                    try (InputStream input = getContentResolver().openInputStream(uri); FileOutputStream output = new FileOutputStream(file)) {
                        if (input == null) throw new IllegalStateException("File is unavailable.");
                        byte[] buffer = new byte[65536]; int length; long bytes = 0;
                        while ((length = input.read(buffer)) != -1) { bytes += length; if (bytes > 150_000_000) throw new IllegalArgumentException("Dataset exceeds 150 MB."); output.write(buffer, 0, length); }
                    }
                    main.post(() -> action("import_json", json("path", file.getAbsolutePath())));
                } else if (request == EXPORT_DRAFT) {
                    JSONObject exported = new JSONObject(bridge.callAttr("dispatch", "export", "{}").toString());
                    try (OutputStream output = getContentResolver().openOutputStream(uri)) {
                        if (output == null) throw new IllegalStateException("Destination is unavailable.");
                        output.write(exported.getString("json").getBytes(StandardCharsets.UTF_8));
                    }
                    main.post(() -> Toast.makeText(this, "Draft exported.", Toast.LENGTH_SHORT).show());
                }
            } catch (Exception e) { fail("Local file operation failed", e); }
        });
    }

    private void showSources() {
        worker.execute(() -> {
            try {
                String content = assetText("DATA_SOURCES.md") + "\n\n" + assetText("SCORING.md") + "\n\n" + assetText("THIRD_PARTY_NOTICES.md")
                        + "\n\nAndroid uses Chaquopy (MIT) with Python 3.12. It requests no Internet permission.";
                main.post(() -> showText("Sources, method and notices", content));
            } catch (Exception e) { fail("Sources unavailable", e); }
        });
    }

    private void showText(String title, String content) {
        TextView text = text(content, 14, TEXT); text.setTextIsSelectable(true); text.setPadding(dp(18), dp(12), dp(18), dp(12));
        new AlertDialog.Builder(this).setTitle(title).setView(scroll(text)).setPositiveButton("Close", null).show();
    }

    private void showPage(boolean analysis) { draftPage.setVisibility(analysis ? View.GONE : View.VISIBLE); analysisPage.setVisibility(analysis ? View.VISIBLE : View.GONE); }
    private JSONObject state() { return viewState.optJSONObject("state"); }
    private void fail(String message, Exception e) {
        android.util.Log.e("LeagueDraft", message, e);
        main.post(() -> { if (!destroyed) { status.setText(message + ": " + e.getMessage()); analysisStatus.setText("Insufficient data or a local operation failed. The draft remains editable."); } });
    }
    private Bitmap portrait(String name) {
        Bitmap bitmap = portraits.get(name);
        if (bitmap == null) {
            try (InputStream input = getAssets().open("icons/" + normalize(name) + ".png")) {
                bitmap = BitmapFactory.decodeStream(input); if (bitmap != null) portraits.put(name, bitmap);
            } catch (Exception ignored) { }
        }
        return bitmap;
    }
    private void copyAsset(String name, File destination) throws Exception {
        File temporary = new File(destination.getPath() + ".installing");
        try (InputStream input = getAssets().open(name); FileOutputStream output = new FileOutputStream(temporary)) {
            byte[] buffer = new byte[65536]; int n; while ((n = input.read(buffer)) != -1) output.write(buffer, 0, n); output.getFD().sync();
        }
        if (!temporary.renameTo(destination)) throw new IllegalStateException("Could not prepare bundled local data.");
    }
    private String assetText(String name) throws Exception {
        try (InputStream input = getAssets().open(name); java.io.ByteArrayOutputStream output = new java.io.ByteArrayOutputStream()) {
            byte[] buffer = new byte[8192]; int n; while ((n = input.read(buffer)) != -1) output.write(buffer, 0, n);
            return output.toString("UTF-8");
        }
    }
    private static String normalize(String value) {
        String raw = Normalizer.normalize(value, Normalizer.Form.NFKD).toLowerCase(Locale.ROOT); StringBuilder result = new StringBuilder();
        for (int i = 0; i < raw.length(); i++) if (Character.isLetterOrDigit(raw.charAt(i))) result.append(raw.charAt(i)); return result.toString();
    }
    private static String capitalize(String value) { return value.substring(0, 1).toUpperCase(Locale.ROOT) + value.substring(1); }
    private static JSONObject json(Object... values) {
        JSONObject object = new JSONObject(); try { for (int i = 0; i < values.length; i += 2) object.put((String) values[i], values[i + 1] == null ? JSONObject.NULL : values[i + 1]); }
        catch (JSONException e) { throw new IllegalArgumentException(e); } return object;
    }
    private static JSONObject targetPayload(String team, String kind, int index, String champion) { return json("team", team, "kind", kind, "index", index, "champion", champion); }
    private List<String> strings(JSONArray values) { List<String> result = new ArrayList<>(); if (values != null) for (int i = 0; i < values.length(); i++) result.add(values.optString(i)); return result; }
    private void setOptions(Spinner spinner, List<String> values, String selected) { setOptions(spinner, values, Math.max(0, values.indexOf(selected))); }
    private void setOptions(Spinner spinner, List<String> values, int selected) {
        boolean same = spinner.getCount() == values.size();
        for (int i = 0; same && i < values.size(); i++) same = values.get(i).equals(spinner.getItemAtPosition(i));
        if (!same) spinner.setAdapter(new ArrayAdapter<>(this, android.R.layout.simple_spinner_dropdown_item, values));
        if (!values.isEmpty() && spinner.getSelectedItemPosition() != selected) spinner.setSelection(selected);
    }
    private AdapterView.OnItemSelectedListener selection(Runnable task) {
        return new AdapterView.OnItemSelectedListener() {
            @Override public void onItemSelected(AdapterView<?> p, View v, int pos, long id) { if (ready && !rendering) task.run(); }
            @Override public void onNothingSelected(AdapterView<?> p) { }
        };
    }
    private Spinner spinner(String[] values, String description) { Spinner result = new Spinner(this); result.setContentDescription(description); result.setAdapter(new ArrayAdapter<>(this, android.R.layout.simple_spinner_dropdown_item, values)); return result; }
    private EditText number(double value) { EditText result = new EditText(this); result.setTextColor(TEXT); result.setInputType(InputType.TYPE_CLASS_NUMBER | InputType.TYPE_NUMBER_FLAG_DECIMAL); result.setText(String.valueOf(value)); return result; }
    private int dp(float value) { return Math.round(value * getResources().getDisplayMetrics().density); }
    private LinearLayout vertical() { LinearLayout layout = new LinearLayout(this); layout.setOrientation(LinearLayout.VERTICAL); return layout; }
    private LinearLayout horizontal() { LinearLayout layout = new LinearLayout(this); layout.setOrientation(LinearLayout.HORIZONTAL); return layout; }
    private LinearLayout.LayoutParams weight() { return new LinearLayout.LayoutParams(0, -2, 1); }
    private ScrollView scroll(View child) { ScrollView view = new ScrollView(this); view.setFillViewport(true); view.addView(child); return view; }
    private TextView text(String value, int size, int color) { TextView view = new TextView(this); view.setText(value); view.setTextSize(size); view.setTextColor(color); return view; }
    private Button button(String value, Runnable task) { Button button = new Button(this); button.setText(value); button.setTextSize(12); button.setAllCaps(false); button.setTextColor(TEXT); button.setMinWidth(0); button.setPadding(dp(4), 0, dp(4), 0); button.setOnClickListener(v -> task.run()); return button; }
    private GradientDrawable background(int fill, int border, int stroke) { GradientDrawable drawable = new GradientDrawable(); drawable.setColor(fill); drawable.setCornerRadius(dp(6)); drawable.setStroke(dp(stroke), border); return drawable; }

    public boolean isReadyForTest() { return ready; }
    public void commandForTest(String command, String arguments) throws JSONException { action(command, new JSONObject(arguments)); }
    public String stateForTest() { return viewState == null ? "{}" : viewState.toString(); }
    @Override protected void onDestroy() { destroyed = true; if (pendingAnalysis != null) main.removeCallbacks(pendingAnalysis); super.onDestroy(); }
}
