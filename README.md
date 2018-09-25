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
  ch = ! git checkout $1 && hunt workon --create
  chb = ! git checkout -b $1 && hunt workon --create
  chm = ! git checkout master && hunt stop
  bd = ! git branch -d $1 && hunt finish
  bdd = ! git branch -D $1 && hunt finish
```

My workflow:

Checking out a branch will start tracking time spent on a task with named after the branch.
Passing the `--create` option means that if the task doesn't already exist it'll be created.
When a task is created you're prompted to make a quick estimate of how long it'll take. It's optional.

Checking out master using `chm` git alias will stop time tracking.

Deleting the branch finishes the task.
