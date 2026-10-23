'use strict';
function statePath(config, fallback) {
    if (config && config.version === 1 && typeof config.stateFile === 'string' &&
        config.stateFile.startsWith('/') && config.stateFile.endsWith('/state.json') &&
        !config.stateFile.includes('\0') && !config.stateFile.split('/').includes('..'))
        return config.stateFile;
    return fallback;
}
module.exports = {statePath};
