# HUNT

HUNT is a CLI TODO list with time tracking.

Why the name HUNT? Tracking. Hunting. Get it? It's a bit of stretch

I wanted a way to track time spent on tasks that was seamless and simple.
For me that meant a cli I could incorporate into my existing git workflow.

## Features

TODO

Just try it. I'll finish this before putting it up on pypi

## Installation

```
git clone https://github.com/AlejandroFrias/hunt
cd hunt
make setup
```

## My git integration
 
```
## ~/.gitconfig

[alias]
  b = branch
  s = status
  st = stash
  d = diff
  a = add
  co = commit
  f = fetch
  p = pull
  bhist = ! git reflog | egrep -io 'moving from ([^[:space:]]+)' | awk '{ print  }' | head
  ch = ! git checkout $1 && hunt --silent workon --create
  chb = ! git checkout -b $1 && read -er -p 'Estimate '$1' (hrs): ' estimate && hunt --silent workon --create --estimate ${estimate:-0}
  chm = ! git checkout master && hunt --silent stop
  bd = ! git branch -d $1 && hunt --silent finish
  bdd = ! git branch -D $1 && hunt --silent finish
```

My workflow:

Use `git chb <branch>` to create new branch and start working on a task created by the same name automatically.
This will prompt to you to enter an estimate (default to 0).

`git ch <branch>` will switch to tracking time in that branch (and create the task if not created yet).

Passing the `--create` option means that if the task doesn't already exist it'll be created.

Passing the `--silent` option prevents any intrusive standard output.

Checking out master using `git chm` will stop time tracking altogether.

Deleting the branch finishes the task.

You can use `hunt estimate` or `hunt edit` to make a new time estimate or edit your start and stop times at any time.

You can us `hunt ls` and it's various options to list out your tasks.
