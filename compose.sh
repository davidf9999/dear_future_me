#!/bin/bash

# Wrapper script for docker compose to enforce branch restrictions for dev/prod profiles.

set -e # Exit immediately if a command exits with a non-zero status.

ACTIVE_PROFILES=()
PASSTHROUGH_ARGS=("$@") # Store all original args

# Iterate through arguments to find active profiles.
# This is a simplified parsing for --profile <name> and --profile=<name>.
for i in "${!PASSTHROUGH_ARGS[@]}"; do
    if [[ "${PASSTHROUGH_ARGS[$i]}" == "--profile" ]]; then
        # Check if next argument exists and is not another option
        if [[ -n "${PASSTHROUGH_ARGS[$((i+1))]}" && ! "${PASSTHROUGH_ARGS[$((i+1))]}" == --* ]]; then
            ACTIVE_PROFILES+=("${PASSTHROUGH_ARGS[$((i+1))]}")
        fi
    elif [[ "${PASSTHROUGH_ARGS[$i]}" == --profile=* ]]; then
        PROFILE_VALUE="${PASSTHROUGH_ARGS[$i]#*=}"
        ACTIVE_PROFILES+=("$PROFILE_VALUE")
    fi
done

# Deduplicate active profiles (though Docker Compose handles multiple declarations)
UNIQUE_ACTIVE_PROFILES=($(echo "${ACTIVE_PROFILES[@]}" | tr ' ' '\n' | sort -u | tr '\n' ' '))

IS_PROD_PROFILE_ACTIVE=false
IS_DEV_PROFILE_ACTIVE=false

for profile in "${UNIQUE_ACTIVE_PROFILES[@]}"; do
    if [[ "$profile" == "prod" ]]; then
        IS_PROD_PROFILE_ACTIVE=true
    elif [[ "$profile" == "dev" ]]; then
        IS_DEV_PROFILE_ACTIVE=true
    fi
done

CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)

# Apply checks only if exactly one of (dev or prod) profile is active.
# If user explicitly runs --profile dev --profile prod, or no profiles, we assume they know.

if [[ "$IS_PROD_PROFILE_ACTIVE" == true && "$IS_DEV_PROFILE_ACTIVE" == false ]]; then
    # Only 'prod' profile is active
    if [[ "$CURRENT_BRANCH" != "main" && "$CURRENT_BRANCH" != "master" ]]; then
        echo "--------------------------------------------------------------------" >&2
        echo "ERROR: Production profile ('--profile prod') can only be run from" >&2
        echo "       the 'main' or 'master' branch." >&2
        echo "       You are currently on branch '$CURRENT_BRANCH'." >&2
        echo "--------------------------------------------------------------------" >&2
        exit 1
    fi
elif [[ "$IS_DEV_PROFILE_ACTIVE" == true && "$IS_PROD_PROFILE_ACTIVE" == false ]]; then
    # Only 'dev' profile is active
    if [[ "$CURRENT_BRANCH" == "main" || "$CURRENT_BRANCH" == "master" ]]; then
        echo "--------------------------------------------------------------------" >&2
        echo "ERROR: Development profile ('--profile dev') should not be run from" >&2
        echo "       the 'main' or 'master' branch to avoid confusion." >&2
        echo "       You are currently on branch '$CURRENT_BRANCH'." >&2
        echo "       Please switch to a development/feature branch." >&2
        echo "--------------------------------------------------------------------" >&2
        exit 1
    fi
fi

echo "Executing: docker compose ${PASSTHROUGH_ARGS[@]}"
docker compose "${PASSTHROUGH_ARGS[@]}"

exit $?