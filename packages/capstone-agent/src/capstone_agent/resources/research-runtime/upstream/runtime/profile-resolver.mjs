// Generated from pinned MIT source; see ../generate.mjs and ../../LICENSE.
export const DEFAULT_PRESETS = {
    default: {
        breadth: 4,
        depth: 2,
        concurrency: 4
    },
    fast: {
        breadth: 2,
        depth: 1,
        concurrency: 2
    },
    deep: {
        breadth: 6,
        depth: 3,
        concurrency: 4
    }
};
export function mergeProfiles(builtin, user) {
    const merged = {
        ...builtin
    };
    for (const [name, override] of Object.entries(user)){
        const base = builtin[name];
        if (base) {
            merged[name] = {
                ...base,
                ...override
            };
        } else {
            merged[name] = {
                breadth: override.breadth ?? 4,
                depth: override.depth ?? 2,
                concurrency: override.concurrency ?? 4,
                maxSearchCalls: override.maxSearchCalls,
                maxElapsedSeconds: override.maxElapsedSeconds
            };
        }
    }
    return merged;
}
export class ProfileResolver {
    presets;
    defaultProfileName;
    constructor(userProfiles, defaultProfileName, builtinPresets){
        const builtin = builtinPresets ?? DEFAULT_PRESETS;
        this.presets = mergeProfiles(builtin, userProfiles);
        this.defaultProfileName = defaultProfileName ?? "default";
    }
    resolve(planProfile) {
        if (planProfile.name !== "custom") {
            return this.presets[planProfile.name] ?? this.presets[this.defaultProfileName] ?? this.presets.default;
        }
        const customPreset = this.presets.custom;
        return {
            breadth: planProfile.breadth ?? customPreset?.breadth ?? 4,
            depth: planProfile.depth ?? customPreset?.depth ?? 2,
            concurrency: planProfile.concurrency ?? customPreset?.concurrency ?? 4,
            maxSearchCalls: customPreset?.maxSearchCalls,
            maxElapsedSeconds: customPreset?.maxElapsedSeconds
        };
    }
    listNames() {
        return Object.keys(this.presets);
    }
    getPresets() {
        return this.presets;
    }
}
